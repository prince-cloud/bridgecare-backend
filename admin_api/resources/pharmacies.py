"""Admin API resources for the pharmacies app (Pharmacy & Inventory, Orders & Payments)."""
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.response import Response

from pharmacies.models import (
    PharmacyProfile,
    Drug,
    DrugCategory,
    DrugBatch,
    StockMovement,
    DrugSupplier,
    Order,
    OrderItem,
    Payment,
    Settlement,
    SettlementOrder,
    SettlementPayout,
    PaymentMethod,
    PharmacyOrder,
    CallBackData,
)
from pharmacies.serializers import (
    PharmacyProfileSerializer,
    ShortPharmacyProfileSerializer,
    DrugCategorySerializer,
    DrugInventorySerializer,
    DrugBatchSerializer,
    StockMovementSerializer,
    SupplierSerializer,
    OrderSerializer,
    PaymentSerializer,
    SettlementListSerializer,
    SettlementDetailSerializer,
    SettlementPayoutSerializer,
    PaymentMethodSerializer,
    SettlementOrderSerializer,
)
from admin_api.base import AdminModelViewSet, AdminReadOnlyViewSet


class DrugAdminSerializer(serializers.ModelSerializer):
    """Plain admin view of a drug — avoids the storefront serializer's
    annotation-dependent computed fields (e.g. nearest_expiry)."""

    pharmacy_name = serializers.CharField(source="pharmacy.pharmacy_name", read_only=True, default=None)
    category_name = serializers.CharField(source="category.name", read_only=True, default=None)

    class Meta:
        model = Drug
        fields = "__all__"


class OrderAdminSerializer(serializers.ModelSerializer):
    """Admin write view of an order — status/amounts editable, the generated
    order number stays read-only."""

    user_email = serializers.CharField(source="user.email", read_only=True, default=None)

    class Meta:
        model = Order
        fields = "__all__"
        read_only_fields = ("order_number", "updated_at")


class PaymentAdminSerializer(serializers.ModelSerializer):
    """Admin write view of a payment."""

    order_number = serializers.CharField(source="order.order_number", read_only=True, default=None)

    class Meta:
        model = Payment
        fields = "__all__"
        read_only_fields = ("reference", "last_updated")


class OrderItemAdminSerializer(serializers.ModelSerializer):
    """Admin write view of an order line item."""

    drug_name = serializers.CharField(source="drug.name", read_only=True, default=None)

    class Meta:
        model = OrderItem
        fields = "__all__"


class PharmacyAdminViewSet(AdminModelViewSet):
    queryset = PharmacyProfile.objects.select_related("user").all()
    serializer_class = PharmacyProfileSerializer
    search_fields = ["pharmacy_name", "email", "pharmacy_license"]
    filterset_fields = ["is_verified", "region"]
    ordering_fields = ["created_at", "pharmacy_name"]
    facet_fields = ["is_verified", "region"]

    @action(detail=True, methods=["post"])
    def verify(self, request, pk=None):
        p = self.get_object(); p.is_verified = True; p.save()
        return Response(PharmacyProfileSerializer(p).data)

    @action(detail=True, methods=["post"])
    def unverify(self, request, pk=None):
        p = self.get_object(); p.is_verified = False; p.save()
        return Response(PharmacyProfileSerializer(p).data)


class DrugAdminViewSet(AdminModelViewSet):
    queryset = Drug.objects.select_related("pharmacy", "category").all()
    serializer_class = DrugAdminSerializer
    search_fields = ["name", "category__name"]
    filterset_fields = ["pharmacy", "category", "base_unit"]
    ordering_fields = ["created_at", "unit_price", "name"]
    facet_fields = ["pharmacy", "base_unit"]


class DrugBatchAdminViewSet(AdminReadOnlyViewSet):
    queryset = DrugBatch.objects.select_related("pharmacy", "drug", "supplier").all()
    serializer_class = DrugBatchSerializer
    search_fields = ["batch_number", "drug__name"]
    filterset_fields = ["pharmacy", "drug", "supplier"]
    ordering_fields = ["expiry_date"]
    facet_fields = ["pharmacy", "drug", "supplier"]


class StockMovementAdminViewSet(AdminReadOnlyViewSet):
    queryset = StockMovement.objects.select_related("pharmacy", "drug").all()
    serializer_class = StockMovementSerializer
    search_fields = ["note", "drug__name"]
    filterset_fields = ["pharmacy", "drug", "reason"]
    ordering_fields = ["created_at"]
    facet_fields = ["pharmacy", "reason"]


class SupplierAdminViewSet(AdminModelViewSet):
    queryset = DrugSupplier.objects.select_related("pharmacy").all()
    serializer_class = SupplierSerializer
    search_fields = ["name", "contact_person", "email"]
    filterset_fields = ["pharmacy"]
    ordering_fields = ["created_at", "name"]
    facet_fields = ["pharmacy"]


class OrderAdminViewSet(AdminModelViewSet):
    queryset = Order.objects.select_related("user").all()
    serializer_class = OrderAdminSerializer
    search_fields = ["order_number", "user__email"]
    filterset_fields = ["status", "payment_status", "delivery_method", "user"]
    ordering_fields = ["created_at", "total_amount"]
    facet_fields = ["status", "payment_status"]

    @action(detail=True, methods=["post"], url_path="change-status")
    def change_status(self, request, pk=None):
        order = self.get_object()
        new_status = request.data.get("status")
        if new_status:
            order.status = new_status
            order.save()
        return Response(OrderAdminSerializer(order).data)


class OrderItemAdminViewSet(AdminModelViewSet):
    queryset = OrderItem.objects.select_related("order", "drug").all()
    serializer_class = OrderItemAdminSerializer
    search_fields = ["drug__name"]
    filterset_fields = ["order", "drug"]
    ordering_fields = ["created_at"]


class PaymentAdminViewSet(AdminModelViewSet):
    queryset = Payment.objects.select_related("order", "user").all()
    serializer_class = PaymentAdminSerializer
    search_fields = ["reference", "order__order_number"]
    filterset_fields = ["status", "order"]
    ordering_fields = ["date_created", "amount"]
    facet_fields = ["status"]


class SettlementAdminViewSet(AdminReadOnlyViewSet):
    queryset = Settlement.objects.select_related("pharmacy").all()
    serializer_class = SettlementListSerializer
    search_fields = ["pharmacy__pharmacy_name"]
    filterset_fields = ["status", "pharmacy"]
    ordering_fields = ["settlement_date"]
    facet_fields = ["pharmacy", "status"]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return SettlementDetailSerializer
        return SettlementListSerializer


class SettlementPayoutAdminViewSet(AdminReadOnlyViewSet):
    queryset = SettlementPayout.objects.select_related("pharmacy", "payment_method").all()
    serializer_class = SettlementPayoutSerializer
    search_fields = ["reference"]
    filterset_fields = ["status", "pharmacy"]
    ordering_fields = ["requested_at"]
    facet_fields = ["pharmacy", "status"]


class PaymentMethodAdminViewSet(AdminReadOnlyViewSet):
    queryset = PaymentMethod.objects.all()
    serializer_class = PaymentMethodSerializer
    filterset_fields = ["payment_method_type", "provider"]
    ordering_fields = ["created_at"]


class DrugCategoryAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = DrugCategory
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at")


class DrugCategoryAdminViewSet(AdminModelViewSet):
    queryset = DrugCategory.objects.all()
    serializer_class = DrugCategoryAdminSerializer
    search_fields = ["name"]
    filterset_fields = ["pharmacy"]
    ordering_fields = ["name"]
    facet_fields = ["pharmacy"]


class PharmacyOrderAdminSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source="order.order_number", read_only=True, default=None)

    class Meta:
        model = PharmacyOrder
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at")


class PharmacyOrderAdminViewSet(AdminReadOnlyViewSet):
    queryset = PharmacyOrder.objects.select_related("pharmacy", "order").all()
    serializer_class = PharmacyOrderAdminSerializer
    search_fields = ["pharmacy__pharmacy_name", "order__order_number"]
    filterset_fields = ["pharmacy", "order", "status"]
    ordering_fields = ["created_at"]
    facet_fields = ["pharmacy", "status"]


class SettlementOrderAdminSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source="order.order_number", read_only=True, default=None)

    class Meta:
        model = SettlementOrder
        fields = "__all__"
        read_only_fields = ("id", "created_at")


class SettlementOrderAdminViewSet(AdminReadOnlyViewSet):
    queryset = SettlementOrder.objects.select_related("settlement", "order").all()
    serializer_class = SettlementOrderAdminSerializer
    search_fields = ["order__order_number"]
    filterset_fields = ["settlement", "order"]
    ordering_fields = ["created_at"]
    facet_fields = ["settlement"]


class CallBackDataAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = CallBackData
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at")


class CallBackDataAdminViewSet(AdminReadOnlyViewSet):
    queryset = CallBackData.objects.all()
    serializer_class = CallBackDataAdminSerializer
    search_fields = ["uuid"]
    filterset_fields = ["callback_type"]
    ordering_fields = ["created_at"]
    facet_fields = ["callback_type"]


def register(router):
    router.register("pharmacies", PharmacyAdminViewSet, basename="admin-pharmacies")
    router.register("drugs", DrugAdminViewSet, basename="admin-drugs")
    router.register("drug-batches", DrugBatchAdminViewSet, basename="admin-drug-batches")
    router.register("stock-movements", StockMovementAdminViewSet, basename="admin-stock-movements")
    router.register("suppliers", SupplierAdminViewSet, basename="admin-suppliers")
    router.register("orders", OrderAdminViewSet, basename="admin-orders")
    router.register("order-items", OrderItemAdminViewSet, basename="admin-order-items")
    router.register("payments", PaymentAdminViewSet, basename="admin-payments")
    router.register("settlements", SettlementAdminViewSet, basename="admin-settlements")
    router.register("settlement-payouts", SettlementPayoutAdminViewSet, basename="admin-settlement-payouts")
    router.register("payment-methods", PaymentMethodAdminViewSet, basename="admin-payment-methods")
    router.register("drug-categories", DrugCategoryAdminViewSet, basename="admin-drug-categories")
    router.register("pharmacy-orders", PharmacyOrderAdminViewSet, basename="admin-pharmacy-orders")
    router.register("settlement-orders", SettlementOrderAdminViewSet, basename="admin-settlement-orders")
    router.register("callback-data", CallBackDataAdminViewSet, basename="admin-callback-data")


EXTRA_URLS = []
