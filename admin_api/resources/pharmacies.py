"""Admin API resources for the pharmacies app (Pharmacy & Inventory, Orders & Payments)."""
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.response import Response

from pharmacies.models import (
    PharmacyProfile,
    Drug,
    DrugBatch,
    StockMovement,
    DrugSupplier,
    Order,
    Payment,
    Settlement,
    SettlementPayout,
    PaymentMethod,
)
from pharmacies.serializers import (
    PharmacyProfileSerializer,
    ShortPharmacyProfileSerializer,
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


class PharmacyAdminViewSet(AdminModelViewSet):
    queryset = PharmacyProfile.objects.select_related("user").all()
    serializer_class = PharmacyProfileSerializer
    search_fields = ["pharmacy_name", "email", "pharmacy_license"]
    filterset_fields = ["is_verified"]
    ordering_fields = ["created_at", "pharmacy_name"]

    def get_serializer_class(self):
        if self.action == "list":
            return ShortPharmacyProfileSerializer
        return PharmacyProfileSerializer

    @action(detail=True, methods=["post"])
    def verify(self, request, pk=None):
        p = self.get_object(); p.is_verified = True; p.save()
        return Response(PharmacyProfileSerializer(p).data)

    @action(detail=True, methods=["post"])
    def unverify(self, request, pk=None):
        p = self.get_object(); p.is_verified = False; p.save()
        return Response(PharmacyProfileSerializer(p).data)


class DrugAdminViewSet(AdminReadOnlyViewSet):
    queryset = Drug.objects.select_related("pharmacy", "category").all()
    serializer_class = DrugAdminSerializer
    filterset_fields = ["pharmacy", "category"]
    ordering_fields = ["created_at"]


class DrugBatchAdminViewSet(AdminReadOnlyViewSet):
    queryset = DrugBatch.objects.select_related("pharmacy", "drug", "supplier").all()
    serializer_class = DrugBatchSerializer
    filterset_fields = ["pharmacy", "drug", "supplier"]
    ordering_fields = ["expiry_date"]


class StockMovementAdminViewSet(AdminReadOnlyViewSet):
    queryset = StockMovement.objects.select_related("pharmacy", "drug").all()
    serializer_class = StockMovementSerializer
    filterset_fields = ["pharmacy", "drug", "reason"]
    ordering_fields = ["created_at"]


class SupplierAdminViewSet(AdminReadOnlyViewSet):
    queryset = DrugSupplier.objects.select_related("pharmacy").all()
    serializer_class = SupplierSerializer
    filterset_fields = ["pharmacy"]
    ordering_fields = ["created_at"]


class OrderAdminViewSet(AdminReadOnlyViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    filterset_fields = ["status", "payment_status", "delivery_method"]
    ordering_fields = ["created_at"]

    @action(detail=True, methods=["post"], url_path="change-status")
    def change_status(self, request, pk=None):
        order = self.get_object()
        new_status = request.data.get("status")
        if new_status:
            order.status = new_status
            order.save()
        return Response(OrderSerializer(order).data)


class PaymentAdminViewSet(AdminReadOnlyViewSet):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    filterset_fields = ["status"]
    ordering_fields = ["date_created"]


class SettlementAdminViewSet(AdminReadOnlyViewSet):
    queryset = Settlement.objects.select_related("pharmacy").all()
    serializer_class = SettlementListSerializer
    filterset_fields = ["status", "pharmacy"]
    ordering_fields = ["settlement_date"]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return SettlementDetailSerializer
        return SettlementListSerializer


class SettlementPayoutAdminViewSet(AdminReadOnlyViewSet):
    queryset = SettlementPayout.objects.select_related("pharmacy").all()
    serializer_class = SettlementPayoutSerializer
    filterset_fields = ["status", "pharmacy"]
    ordering_fields = ["requested_at"]


class PaymentMethodAdminViewSet(AdminReadOnlyViewSet):
    queryset = PaymentMethod.objects.all()
    serializer_class = PaymentMethodSerializer
    filterset_fields = ["payment_method_type", "provider"]
    ordering_fields = ["created_at"]


def register(router):
    router.register("pharmacies", PharmacyAdminViewSet, basename="admin-pharmacies")
    router.register("drugs", DrugAdminViewSet, basename="admin-drugs")
    router.register("drug-batches", DrugBatchAdminViewSet, basename="admin-drug-batches")
    router.register("stock-movements", StockMovementAdminViewSet, basename="admin-stock-movements")
    router.register("suppliers", SupplierAdminViewSet, basename="admin-suppliers")
    router.register("orders", OrderAdminViewSet, basename="admin-orders")
    router.register("payments", PaymentAdminViewSet, basename="admin-payments")
    router.register("settlements", SettlementAdminViewSet, basename="admin-settlements")
    router.register("payouts", SettlementPayoutAdminViewSet, basename="admin-payouts")
    router.register("payment-methods", PaymentMethodAdminViewSet, basename="admin-payment-methods")


EXTRA_URLS = []
