from decimal import Decimal
from django.db import transaction
from django.http import HttpRequest
from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.views import APIView
from helpers import exceptions
from pharmacies.permissions import PharmacyProfileRequired
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
from django.db.models import Q, Sum, Min
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


class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [PharmacyProfileRequired]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    http_method_names = ["get", "post", "patch"]


class PlanceOrderView(APIView):
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
                quantity=quantity,
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
