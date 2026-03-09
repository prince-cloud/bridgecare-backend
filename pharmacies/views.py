from decimal import Decimal
from django.db import transaction
from django.http import HttpRequest
from rest_framework import viewsets, permissions, filters, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.views import APIView
from helpers import exceptions
from pharmacies.permissions import PharmacyProfileRequired
from .filters import OrderFilter
from .models import (
    DrugBatch,
    DrugSupplier,
    OrderItem,
    PharmacyOrder,
    PharmacyProfile,
    Drug,
    StockMovement,
    DrugCategory,
    Order,
    Payment,
)
from patients.models import Visitation, Prescription
from accounts.serializers import AddressSerializer, ShortUserSerializer
from .serializers import (
    DrugBatchCreateSerializer,
    DrugBatchSerializer,
    DrugSerializer,
    GetPrescriptionSerializer,
    PharmacyProfileSerializer,
    DrugInventorySerializer,
    DrugStockHistorySerializer,
    DrugCategorySerializer,
    StockMovementCreateSerializer,
    StockMovementSerializer,
    SupplierSerializer,
    OrderSerializer,
    PaymentSerializer,
    InitiatePaymentSerializer,
    VerifyPaymentSerializer,
    PlaceOrderSerializer,
)
from django.db.models import Q, Sum, Min, Max
from django.db.models.functions import TruncMonth
from django.utils import timezone
from api.paystack import PayStack
import json
from django.conf import settings

paystack = PayStack()


class PharmacyProfileViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing pharmacy profiles
    """

    queryset = PharmacyProfile.objects.all()
    serializer_class = PharmacyProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = [
        "license_expiry_date",
        "district",
        "region",
        "delivery_available",
    ]
    search_fields = ["user__email", "pharmacy_name", "pharmacy_license", "district"]
    ordering_fields = ["pharmacy_name"]
    ordering = ["pharmacy_name"]

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]

    @action(
        detail=False, methods=["get"], permission_classes=[permissions.IsAuthenticated]
    )
    def nearby_pharmacies(self, request):
        """Get pharmacies near a location"""
        latitude = request.query_params.get("lat")
        longitude = request.query_params.get("lng")

        if not latitude or not longitude:
            return Response(
                {"error": "Latitude and longitude are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Simple distance calculation (in production, use PostGIS or similar)
        queryset = self.get_queryset().filter(
            latitude__isnull=False, longitude__isnull=False, user__is_active=True
        )

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def me(self, request):
        """Get current user's pharmacy profile"""
        try:
            profile = request.user.pharmacy_profile
            serializer = self.get_serializer(profile)
            return Response(serializer.data)
        except PharmacyProfile.DoesNotExist:
            return Response(
                {"error": "Pharmacy profile not found"},
                status=status.HTTP_404_NOT_FOUND,
            )


class InventoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for managing pharmacy inventory with search, pagination, and ordering
    """

    serializer_class = DrugInventorySerializer
    permission_classes = [PharmacyProfileRequired]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    search_fields = ["name", "category__name", "base_unit"]
    ordering_fields = [
        "name",
        "available_quantity",
        "nearest_expiry",
        "unit_price",
        "created_at",
    ]
    ordering = ["name"]

    def get_queryset(self):
        """Get inventory for the current pharmacy with annotations"""
        today = timezone.now().date()
        pharmacy = self.request.user.pharmacy_profile

        queryset = (
            Drug.objects.filter(pharmacy=pharmacy).annotate(
                available_quantity=Sum(
                    "movements__quantity",
                    filter=Q(movements__batch__expiry_date__gte=today),
                ),
                nearest_expiry=Min(
                    "batches__expiry_date",
                    filter=Q(batches__expiry_date__gte=today),
                ),
            )
            # .filter(available_quantity__gte=0)
            .select_related("category")
        )
        return queryset

    @action(
        detail=True,
        methods=["get"],
        url_path="history",
        url_name="history",
    )
    def history(self, request, pk=None):
        """Confirm an appointment"""
        drug = self.get_object()

        history = StockMovement.objects.exclude(
            reason__in=[StockMovement.Reason.SALE],
        ).filter(drug=drug)

        return Response(
            data=DrugStockHistorySerializer(
                history, many=True, context={"request": request}
            ).data,
            status=status.HTTP_200_OK,
        )

    @action(
        detail=True,
        methods=["get"],
        url_path="order-history",
        url_name="order-history",
    )
    def order_history(self, request, pk=None):
        """
        Get order history for a specific inventory drug.
        """
        drug = self.get_object()
        pharmacy = request.user.pharmacy_profile

        items = (
            OrderItem.objects.filter(drug=drug)
            .select_related("order")
            .prefetch_related("order__pharmacy_orders")
            .order_by("-order__created_at", "-created_at")
        )

        history = []
        for item in items:
            pharmacy_order = next(
                (
                    po
                    for po in item.order.pharmacy_orders.all()
                    if po.pharmacy_id == pharmacy.id
                ),
                None,
            )
            history.append(
                {
                    "order_number": item.order.order_number,
                    "order_date": item.order.created_at,
                    "quantity_ordered": item.quantity,
                    "unit_price": item.unit_price,
                    "total_price": item.total_price,
                    "status": (
                        pharmacy_order.status
                        if pharmacy_order
                        else PharmacyOrder.Status.PENDING
                    ),
                }
            )

        return Response(
            data={
                "drug_id": str(drug.id),
                "drug_name": drug.name,
                "order_history": history,
            },
            status=status.HTTP_200_OK,
        )

    @action(
        detail=True,
        methods=["get"],
        url_path="sales-history",
        url_name="sales-history",
    )
    def sales_history(self, request, pk=None):
        """
        Get monthly sales summary for a specific inventory drug.
        """
        drug = self.get_object()
        pharmacy = request.user.pharmacy_profile
        current_year = timezone.now().year

        sales_items = (
            OrderItem.objects.filter(
                drug=drug,
                order__pharmacy_orders__pharmacy=pharmacy,
                order__created_at__year=current_year,
            )
            .exclude(
                order__pharmacy_orders__status__in=[
                    PharmacyOrder.Status.CANCELLED,
                    PharmacyOrder.Status.REFUNDED,
                ]
            )
            .distinct()
            .order_by("-order__created_at")
        )

        totals = sales_items.aggregate(
            total_units_sold=Sum("quantity"),
            total_revenue=Sum("total_price"),
            last_sale_date=Max("order__created_at"),
        )

        monthly_sales = (
            sales_items.annotate(month=TruncMonth("order__created_at"))
            .values("month")
            .annotate(
                total_quantity_sold=Sum("quantity"),
                total_amount=Sum("total_price"),
            )
            .order_by("-month")
        )

        monthly_report = [
            {
                "month": entry["month"].strftime("%B") if entry["month"] else None,
                "total_quantity_sold": entry["total_quantity_sold"] or 0,
                "total_amount": entry["total_amount"] or Decimal("0.00"),
            }
            for entry in monthly_sales
        ]

        return Response(
            data={
                "drug_id": str(drug.id),
                "drug_name": drug.name,
                "year": current_year,
                "total_units_sold": totals.get("total_units_sold") or 0,
                "total_revenue": totals.get("total_revenue") or Decimal("0.00"),
                "last_sale_date": totals.get("last_sale_date"),
                "monthly_report": monthly_report,
            },
            status=status.HTTP_200_OK,
        )

    @action(
        detail=False,
        methods=["post"],
        url_path="get-prescription",
        url_name="get-prescription",
        permission_classes=[permissions.IsAuthenticated],
        serializer_class=GetPrescriptionSerializer,
    )
    def get_prescription(self, request):
        """
        Get prescription drugs and match with pharmacy inventory.
        Returns available and unavailable drugs separately.
        """
        serializer = GetPrescriptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        prescription_code = serializer.validated_data["prescription_code"]

        try:
            # Get visitation with that prescription code
            visitation = Visitation.objects.get(prescription_code=prescription_code)
        except Visitation.DoesNotExist:
            return Response(
                {"error": "Prescription not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Get prescriptions for that visitation
        prescriptions = Prescription.objects.filter(visitation=visitation)

        # Get available drugs in pharmacy inventory
        drug_queryset = self.get_queryset()

        # Separate available and unavailable drugs
        available_drugs = []
        unavailable_drugs = []

        for prescription in prescriptions:
            medication_name = (
                prescription.medication.strip().lower()
                if prescription.medication
                else ""
            )

            if not medication_name:
                continue

            # Try to find matching drug in inventory
            matched_drug = None

            # First, try exact match (case-insensitive)
            for drug in drug_queryset:
                if medication_name == drug.name.lower():
                    matched_drug = drug
                    break

            # If no exact match, try partial match (medication name in drug name)
            if not matched_drug:
                for drug in drug_queryset:
                    if (
                        medication_name in drug.name.lower()
                        or drug.name.lower() in medication_name
                    ):
                        matched_drug = drug
                        break

            if matched_drug:
                # Drug is available in inventory
                drug_data = DrugInventorySerializer(
                    matched_drug,
                    context={"request": request},
                ).data
                # Add prescription details to the drug data
                drug_data["prescription"] = {
                    "id": prescription.id,
                    "medication": prescription.medication,
                    "dosage": prescription.dosage,
                    "frequency": prescription.frequency,
                    "duration": prescription.duration,
                    "instructions": prescription.instructions,
                }
                available_drugs.append(drug_data)
            else:
                # Drug is not available in inventory
                unavailable_drugs.append(
                    {
                        "prescription": {
                            "id": prescription.id,
                            "medication": prescription.medication,
                            "dosage": prescription.dosage,
                            "frequency": prescription.frequency,
                            "duration": prescription.duration,
                            "instructions": prescription.instructions,
                        },
                        "available": False,
                        "message": f"{prescription.medication} is not available in this pharmacy",
                    }
                )

        return Response(
            {
                "prescription_code": prescription_code,
                "available_drugs": available_drugs,
                "unavailable_drugs": unavailable_drugs,
                "summary": {
                    "total_prescribed": len(prescriptions),
                    "available_count": len(available_drugs),
                    "unavailable_count": len(unavailable_drugs),
                },
            },
            status=status.HTTP_200_OK,
        )


class DrugCategoryViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing drug categories
    """

    queryset = DrugCategory.objects.all()
    serializer_class = DrugCategorySerializer
    permission_classes = [PharmacyProfileRequired]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    http_method_names = ["get", "post", "patch", "delete"]

    def perform_create(self, serializer):
        serializer.save(pharmacy=self.request.user.pharmacy_profile)


class DrugViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing drugs
    """

    queryset = Drug.objects.all()
    serializer_class = DrugSerializer
    permission_classes = [PharmacyProfileRequired]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    http_method_names = ["get", "post", "patch"]

    def get_queryset(self):
        pharmacy = self.request.user.pharmacy_profile
        return self.queryset.filter(pharmacy=pharmacy)

    def perform_create(self, serializer):
        serializer.save(pharmacy=self.request.user.pharmacy_profile)


class SupplierViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing suppliers
    """

    queryset = DrugSupplier.objects.all()
    serializer_class = SupplierSerializer
    permission_classes = [PharmacyProfileRequired]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    http_method_names = ["get", "post", "patch"]

    def get_queryset(self):
        pharmacy = self.request.user.pharmacy_profile
        return self.queryset.filter(pharmacy=pharmacy)

    def perform_create(self, serializer):
        serializer.save(pharmacy=self.request.user.pharmacy_profile)


class DrugBatchViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing drug batches
    """

    queryset = DrugBatch.objects.all()
    serializer_class = DrugBatchSerializer
    permission_classes = [PharmacyProfileRequired]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    http_method_names = ["get", "post", "patch"]

    def get_serializer_class(self):
        if self.action == "create":
            return DrugBatchCreateSerializer
        return DrugBatchSerializer

    def get_queryset(self):
        pharmacy = self.request.user.pharmacy_profile
        return self.queryset.filter(pharmacy=pharmacy)

    def perform_create(self, serializer):
        serializer.save(pharmacy=self.request.user.pharmacy_profile)


class StockMovementViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing stock movements
    """

    queryset = StockMovement.objects.all()
    serializer_class = StockMovementSerializer
    permission_classes = [PharmacyProfileRequired]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    http_method_names = ["get", "post", "patch"]

    def get_serializer_class(self):
        if self.action == "create":
            return StockMovementCreateSerializer
        return StockMovementSerializer

    def get_queryset(self):
        pharmacy = self.request.user.pharmacy_profile
        return self.queryset.filter(pharmacy=pharmacy)

    def perform_create(self, serializer):
        serializer.save(pharmacy=self.request.user.pharmacy_profile)


class PaymentViewset(viewsets.ModelViewSet):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post"]

    @transaction.atomic
    @action(
        methods=["post"],
        detail=False,
        url_path="initiate-payment",
        url_name="initiate-payment",
        serializer_class=InitiatePaymentSerializer,
    )
    def initiate_payment(self, request: HttpRequest):
        """
        the intiate payment view created model for payment and amount
        and also makes such donation as anonymouse.
        """

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = serializer.validated_data["order"]

        # create a payment model
        try:
            callback_url = settings.PAYSTACK_CALLBACK_URL
            payment = Payment.objects.create(
                user=request.user,
                order=serializer.validated_data["order"],
                amount=order.total_amount,
            )
            # get payment email
            payment_email = payment.user.email if payment.user else "info@wefund.help"

            # paystack_amount = payment.
            _, response = paystack.initialize_payment(
                data={
                    "amount": str(payment.amount_value()),
                    "email": payment_email,
                    "reference": payment.reference,
                    "currency": "GHS",
                    "callback_url": callback_url,
                }
            )

            payment.payment_response = json.dumps(response)
            results = json.dumps(response)
            payment.authorization_url = (
                response["authorization_url"]
                if "authorization_url" in results
                else None
            )
            payment.save()

        except Exception as e:
            print("===== error: ", e)
            raise exceptions.GeneralException(detail=str(e))

        return Response(
            data=PaymentSerializer(instance=payment).data,
            status=status.HTTP_200_OK,
        )

    @action(
        methods=["post"],
        detail=False,
        url_path="verify-payment",
        url_name="verify-payment",
        serializer_class=VerifyPaymentSerializer,
    )
    def verify_payment(self, request: HttpRequest):
        """
        this view allows you to verify if a payment has been made
        and completed
        """
        # payment = self.get_object()
        serializer = VerifyPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment = serializer.validated_data["reference"]

        print("=== transaciton refer: ", payment.amount_value())

        # verify payment from paystack
        _, response = paystack.verify_payment(
            ref=payment.reference,
            amount=payment.amount_value(),
        )

        req_status = response.get("status", "failed")
        if req_status == "success":
            # lets create a donation object
            # paystack_charge = float(float(1.9 / 100) * float(payment.total_amount))
            payment.order.payment_status = Order.PaymentStatus.PAID
            payment.payment_response = response
            payment.status = Payment.Status.COMPLETED
            payment.save()
            payment.order.save()

            return Response(data={"status": req_status})

        return Response(
            data={
                "status": req_status,
            },
            status=status.HTTP_200_OK,
        )


class OrderPagination(PageNumberPagination):
    """Pagination for orders list with 'orders' key for consistency."""

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100

    def get_paginated_response(self, data):
        from collections import OrderedDict

        return Response(
            OrderedDict(
                [
                    ("count", self.page.paginator.count),
                    ("next", self.get_next_link()),
                    ("previous", self.get_previous_link()),
                    ("orders", data),
                ]
            )
        )


class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [PharmacyProfileRequired]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_class = OrderFilter
    pagination_class = OrderPagination
    search_fields = ["order_number"]
    ordering_fields = ["created_at", "updated_at", "total_amount"]
    ordering = ["-created_at"]
    http_method_names = ["get", "post", "patch"]

    def get_queryset(self):
        """Return orders for the current user's pharmacy only."""
        if not hasattr(self.request.user, "pharmacy_profile"):
            return Order.objects.none()
        return (
            Order.objects.filter(
                pharmacy_orders__pharmacy=self.request.user.pharmacy_profile
            )
            .select_related("address", "user")
            .prefetch_related("pharmacy_orders__pharmacy", "items__drug__pharmacy")
            .distinct()
            .order_by("-created_at")
        )

    def _build_grouped_order(self, order, pharmacy, request):
        """Build order representation with only items from the requesting pharmacy."""
        pharmacy_order = order.pharmacy_orders.filter(pharmacy=pharmacy).first()
        status_value = (
            pharmacy_order.status if pharmacy_order else PharmacyOrder.Status.PENDING
        )

        items = []
        for item in order.items.filter(drug__pharmacy=pharmacy).select_related(
            "drug__category"
        ):
            drug = item.drug
            drug_detail = {
                "id": str(drug.id),
                "name": drug.name,
                "base_unit": drug.base_unit,
                "category": drug.category.name if drug.category_id else None,
                "image": (
                    request.build_absolute_uri(drug.image.url) if drug.image else None
                ),
            }
            items.append(
                {
                    "id": str(item.id),
                    "drug": drug_detail,
                    "drug_id": str(item.drug.id),
                    "drug_name": item.drug.name,
                    "quantity": item.quantity,
                    "unit_price": item.unit_price,
                    "total_price": item.total_price,
                    "status": status_value,
                    "created_at": item.created_at,
                }
            )

        user_data = ShortUserSerializer(order.user, context={"request": request}).data
        delivery_address = None
        if order.address_id:
            delivery_address = AddressSerializer(
                order.address, context={"request": request}
            ).data

        return {
            "id": str(order.id),
            "order_number": order.order_number,
            "user": user_data,
            "status": order.status,
            "payment_status": order.payment_status,
            "subtotal": order.subtotal,
            "delivery_fee": order.delivery_fee,
            "total_amount": order.total_amount,
            "delivery_method": order.delivery_method,
            "address": str(order.address_id) if order.address_id else None,
            "delivery_address": delivery_address,
            "created_at": order.created_at,
            "updated_at": order.updated_at,
            "delivered_at": order.delivered_at,
            "items": items,
        }

    def list(self, request: HttpRequest, *args, **kwargs):
        """Return orders for the pharmacy with only items from their pharmacy."""
        pharmacy = request.user.pharmacy_profile
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            grouped_orders = [
                self._build_grouped_order(order, pharmacy, request) for order in page
            ]
            return self.get_paginated_response(grouped_orders)
        grouped_orders = [
            self._build_grouped_order(order, pharmacy, request) for order in queryset
        ]
        return Response(
            data={"orders": grouped_orders},
            status=status.HTTP_200_OK,
        )

    def retrieve(self, request: HttpRequest, *args, **kwargs):
        """Return a single order with only items from the pharmacy."""
        instance = self.get_object()
        pharmacy = request.user.pharmacy_profile
        grouped = self._build_grouped_order(instance, pharmacy, request)
        return Response(data=grouped, status=status.HTTP_200_OK)

    @action(
        methods=["get"],
        detail=False,
        url_path="my-orders",
        url_name="my-orders",
        permission_classes=[permissions.IsAuthenticated],
    )
    def my_orders(self, request: HttpRequest):
        """
        Return the authenticated user's orders grouped by pharmacy.
        Used by customers to view their order history.
        """
        orders = (
            request.user.orders.select_related("address")
            .prefetch_related("pharmacy_orders__pharmacy", "items__drug__pharmacy")
            .order_by("-created_at")
        )
        grouped_orders = []
        for order in orders:
            pharmacy_groups = {}
            for pharmacy_order in order.pharmacy_orders.all():
                pharmacy = pharmacy_order.pharmacy
                pharmacy_groups[str(pharmacy.id)] = {
                    "pharmacy_id": str(pharmacy.id),
                    "pharmacy_name": pharmacy.pharmacy_name,
                    "status": pharmacy_order.status,
                    "items": [],
                }
            for item in order.items.all():
                pharmacy = item.drug.pharmacy
                pharmacy_id = str(pharmacy.id)
                if pharmacy_id not in pharmacy_groups:
                    pharmacy_groups[pharmacy_id] = {
                        "pharmacy_id": pharmacy_id,
                        "pharmacy_name": pharmacy.pharmacy_name,
                        "status": PharmacyOrder.Status.PENDING,
                        "items": [],
                    }
                pharmacy_groups[pharmacy_id]["items"].append(
                    {
                        "id": str(item.id),
                        "drug_id": str(item.drug.id),
                        "drug_name": item.drug.name,
                        "quantity": item.quantity,
                        "unit_price": item.unit_price,
                        "total_price": item.total_price,
                        "status": pharmacy_groups[pharmacy_id]["status"],
                        "created_at": item.created_at,
                    }
                )
            grouped_orders.append(
                {
                    "id": str(order.id),
                    "order_number": order.order_number,
                    "status": order.status,
                    "payment_status": order.payment_status,
                    "subtotal": order.subtotal,
                    "delivery_fee": order.delivery_fee,
                    "total_amount": order.total_amount,
                    "delivery_method": order.delivery_method,
                    "address": str(order.address_id) if order.address_id else None,
                    "created_at": order.created_at,
                    "updated_at": order.updated_at,
                    "delivered_at": order.delivered_at,
                    "pharmacies": list(pharmacy_groups.values()),
                }
            )
        return Response(
            data={"orders": grouped_orders},
            status=status.HTTP_200_OK,
        )

    def _get_pharmacy_order(self, order, pharmacy):
        """Get or create PharmacyOrder for this pharmacy and order."""
        pharmacy_order, _ = PharmacyOrder.objects.get_or_create(
            pharmacy=pharmacy,
            order=order,
            defaults={"status": PharmacyOrder.Status.PENDING},
        )
        return pharmacy_order

    def _sync_order_status(self, order):
        """
        Sync Order.status from PharmacyOrder statuses.
        - Single pharmacy: direct 1:1, any PharmacyOrder change reflects on Order.
        - Multiple pharmacies: Order = PROCESSING until all confirm, then Order mirrors
          the agreed status (CONFIRMED, READY, etc.). Each PharmacyOrder keeps its own status.
        """
        pharmacy_orders = list(order.pharmacy_orders.all())
        if not pharmacy_orders:
            return
        statuses = {po.status for po in pharmacy_orders}

        if len(pharmacy_orders) == 1:
            po_status = pharmacy_orders[0].status
            order.status = po_status
            update_fields = ["status", "updated_at"]
            if po_status == PharmacyOrder.Status.DELIVERED and not order.delivered_at:
                order.delivered_at = timezone.now()
                update_fields.append("delivered_at")
            if po_status == PharmacyOrder.Status.REFUNDED:
                order.payment_status = Order.PaymentStatus.REFUNDED
                update_fields.append("payment_status")
            order.save(update_fields=update_fields)
            return

        if statuses == {PharmacyOrder.Status.DELIVERED}:
            order.status = Order.Status.DELIVERED
            if not order.delivered_at:
                order.delivered_at = timezone.now()
            order.save(update_fields=["status", "delivered_at", "updated_at"])
        elif statuses == {PharmacyOrder.Status.CANCELLED}:
            order.status = Order.Status.CANCELLED
            order.save(update_fields=["status", "updated_at"])
        elif statuses == {PharmacyOrder.Status.REFUNDED}:
            order.status = Order.Status.REFUNDED
            order.payment_status = Order.PaymentStatus.REFUNDED
            order.save(update_fields=["status", "payment_status", "updated_at"])
        elif statuses == {PharmacyOrder.Status.READY}:
            order.status = Order.Status.READY
            order.save(update_fields=["status", "updated_at"])
        elif statuses == {PharmacyOrder.Status.DELIVERING}:
            order.status = Order.Status.DELIVERING
            order.save(update_fields=["status", "updated_at"])
        elif statuses == {PharmacyOrder.Status.CONFIRMED}:
            order.status = Order.Status.CONFIRMED
            order.save(update_fields=["status", "updated_at"])
        elif statuses == {PharmacyOrder.Status.PROCESSING}:
            order.status = Order.Status.PROCESSING
            order.save(update_fields=["status", "updated_at"])
        elif (
            PharmacyOrder.Status.CANCELLED not in statuses
            and PharmacyOrder.Status.REFUNDED not in statuses
        ):
            if statuses & {
                PharmacyOrder.Status.CONFIRMED,
                PharmacyOrder.Status.PROCESSING,
                PharmacyOrder.Status.READY,
                PharmacyOrder.Status.DELIVERING,
                PharmacyOrder.Status.DELIVERED,
            }:
                order.status = Order.Status.PROCESSING
                order.save(update_fields=["status", "updated_at"])

    _PHARMACY_ORDER_STATUS_MAP = {
        "pending": PharmacyOrder.Status.PENDING,
        "confirmed": PharmacyOrder.Status.CONFIRMED,
        "processing": PharmacyOrder.Status.PROCESSING,
        "ready": PharmacyOrder.Status.READY,
        "shipped": PharmacyOrder.Status.DELIVERING,
        "delivering": PharmacyOrder.Status.DELIVERING,
        "delivered": PharmacyOrder.Status.DELIVERED,
        "cancelled": PharmacyOrder.Status.CANCELLED,
        "refunded": PharmacyOrder.Status.REFUNDED,
    }

    @action(detail=True, methods=["post", "patch"], url_path="update-status")
    def update_status(self, request, pk=None):
        """
        Update the pharmacy's fulfillment status for this order.
        Accepts status in query param or body. Can move status back and forth.
        Valid statuses: pending, confirmed, processing, ready, shipped, delivering, delivered, cancelled, refunded
        """
        status_value = request.data.get("status") or request.query_params.get("status")
        if not status_value:
            return Response(
                {"error": "status is required (query param or body)"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        status_value = str(status_value).lower().strip()

        if status_value not in self._PHARMACY_ORDER_STATUS_MAP:
            return Response(
                {
                    "error": "Invalid status",
                    "valid_statuses": list(self._PHARMACY_ORDER_STATUS_MAP.keys()),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        order = self.get_object()
        pharmacy = request.user.pharmacy_profile
        pharmacy_order = self._get_pharmacy_order(order, pharmacy)
        pharmacy_order.status = self._PHARMACY_ORDER_STATUS_MAP[status_value]
        pharmacy_order.save(update_fields=["status", "updated_at"])

        # Refetch order so _sync_order_status sees fresh pharmacy_orders (prefetch was stale)
        order = (
            Order.objects.filter(pk=order.pk)
            .prefetch_related("pharmacy_orders")
            .first()
        )
        self._sync_order_status(order)

        # Refetch again with full relations for response
        order = (
            Order.objects.filter(pk=order.pk)
            .select_related("address", "user")
            .prefetch_related(
                "pharmacy_orders__pharmacy",
                "items__drug__pharmacy",
                "items__drug__category",
            )
            .first()
        )
        grouped = self._build_grouped_order(order, pharmacy, request)
        return Response(data=grouped, status=status.HTTP_200_OK)


class PlaceOrderView(APIView):
    serializer_class = PlaceOrderSerializer
    permission_classes = [permissions.AllowAny]

    @transaction.atomic
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        current_user = self.request.user

        # create order object
        order = Order.objects.create(
            user=current_user,
            delivery_method=data.get("delivery_method"),
            subtotal=0,
            total_amount=0,
        )
        # create order items
        order_items = data.get("items")
        for order_item in order_items:
            print(order_item)
            drug_id = order_item.get("drug")
            quantity = order_item.get("quantity")

            # get drug object
            drug = Drug.objects.get(id=drug_id)
            pharmacy = drug.pharmacy

            # get current btach
            today = timezone.now().today()
            batch = drug.batches.filter(expiry_date__gte=today).first()

            # create a movement item
            _ = StockMovement.objects.create(
                pharmacy=drug.pharmacy,
                drug=drug,
                batch=batch,
                quantity=-quantity,
                reason=StockMovement.Reason.SALE,
            )

            # create order item
            order_item = OrderItem.objects.create(
                order=order,
                drug=drug,
                quantity=quantity,
                unit_price=drug.unit_price,
                total_price=Decimal(drug.unit_price * quantity),
            )

            # create pharmacy order object
            if not PharmacyOrder.objects.filter(
                pharmacy=pharmacy, order=order
            ).exists():
                _ = PharmacyOrder.objects.create(pharmacy=pharmacy, order=order)

            order.subtotal += order_item.total_price
            order.total_amount = order.subtotal
            order.save()

        return Response(
            data=OrderSerializer(
                instance=order, many=False, context={"request": request}
            ).data,
            status=status.HTTP_201_CREATED,
        )
