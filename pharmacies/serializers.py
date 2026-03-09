from rest_framework import serializers
from .models import (
    PharmacyProfile,
    Drug,
    DrugBatch,
    DrugSupplier,
    DrugCategory,
    StockMovement,
    Order,
    OrderItem,
    Payment,
    Settlement,
    SettlementOrder,
)
from accounts.serializers import UserSerializer
from django.utils import timezone
from helpers import exceptions


class PharmacyProfileSerializer(serializers.ModelSerializer):
    """
    Pharmacy profile serializer
    """

    user = UserSerializer(read_only=True)

    class Meta:
        model = PharmacyProfile
        fields = (
            "id",
            "user",
            "pharmacy_name",
            "pharmacy_license",
            "license_expiry_date",
            "address",
            "district",
            "region",
            "latitude",
            "longitude",
            "phone_number",
            "email",
            "website",
            "delivery_available",
            "delivery_radius",
            "pharmacist_license",
            "license_expiry_date",
            "is_verified",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class ShortPharmacyProfileSerializer(serializers.ModelSerializer):
    """
    Pharmacy profile serializer
    """

    class Meta:
        model = PharmacyProfile
        fields = (
            "id",
            "pharmacy_name",
            "address",
            "district",
            "region",
            "latitude",
            "longitude",
            "phone_number",
            "email",
            "delivery_available",
            "delivery_radius",
        )
        read_only_fields = ("id",)


class DrugCategorySerializer(serializers.ModelSerializer):
    """
    Drug category serializer
    """

    is_owner = serializers.SerializerMethodField()

    def get_is_owner(self, obj):
        pharmacy = self.context["request"].user.pharmacy_profile
        return obj.pharmacy == pharmacy

    class Meta:
        model = DrugCategory
        fields = (
            "id",
            "name",
            "is_owner",
        )
        read_only_fields = ("id",)


class DrugSupplierSerializer(serializers.ModelSerializer):

    class Meta:
        model = DrugSupplier
        fields = ("id", "name", "phone_number", "email", "address")
        read_only_fields = ("id",)


class DrugInventorySerializer(serializers.ModelSerializer):
    available_quantity = serializers.IntegerField(read_only=True)
    nearest_expiry = serializers.DateField(read_only=True)

    is_expired = serializers.SerializerMethodField()
    low_quantity = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    category = DrugCategorySerializer(read_only=True)

    class Meta:
        model = Drug
        fields = [
            "id",
            "image",
            "name",
            "base_unit",
            "unit_price",
            "available_quantity",
            "nearest_expiry",
            "is_expired",
            "low_quantity",
            "status",
            "category",
        ]

    def get_is_expired(self, obj):
        if not obj.nearest_expiry:
            return False
        return obj.nearest_expiry < timezone.now().date()

    def get_low_quantity(self, obj):
        return (obj.available_quantity or 0) <= obj.low_stock_threshold

    def get_status(self, obj):
        qty = obj.available_quantity or 0
        threshold = obj.low_stock_threshold

        if qty <= 0:
            return "OUT OF STOCK"
        elif qty <= threshold:
            return "LOW STOCK"
        return "IN STOCK"


class DrugStockHistorySerializer(serializers.ModelSerializer):
    """
    Drug stock history serializer
    """

    previsous_quantity = serializers.SerializerMethodField()

    def get_previsous_quantity(self, obj):
        """
        Get the quantity from the previous StockMovement record (created before this one).
        Returns None if this is the first movement for the drug.
        """
        # Get the previous StockMovement for the same drug and pharmacy, ordered by creation time
        previous_movement = (
            StockMovement.objects.filter(
                drug=obj.drug,
                pharmacy=obj.pharmacy,
                created_at__lt=obj.created_at,
            )
            .order_by("-created_at")
            .first()
        )

        if previous_movement:
            return previous_movement.quantity
        return None

    class Meta:
        model = StockMovement
        fields = (
            "id",
            "drug",
            "batch",
            "quantity",
            "previsous_quantity",
            "reason",
            "note",
            "created_at",
        )
        read_only_fields = ("id", "created_at")


class GetPrescriptionSerializer(serializers.Serializer):
    """
    Get prescription serializer
    """

    prescription_code = serializers.CharField(required=True)


class OrderItemSerializer(serializers.ModelSerializer):
    """
    Order item serializer
    """

    # drug = DrugSerializer(read_only=True)

    class Meta:
        model = OrderItem
        fields = (
            "id",
            "drug",
            "quantity",
            "unit_price",
            "total_price",
            "created_at",
        )
        read_only_fields = ("id", "created_at")


class OrderSerializer(serializers.ModelSerializer):
    """
    Order serializer with items
    """

    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = (
            "id",
            "order_number",
            "user",
            "status",
            "payment_status",
            "subtotal",
            "delivery_fee",
            "total_amount",
            "delivery_method",
            "address",
            "items",
            "created_at",
            "updated_at",
            "delivered_at",
        )
        read_only_fields = (
            "id",
            "order_number",
            "user",
            "created_at",
            "updated_at",
            "delivered_at",
        )


class OrderCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating orders from cart
    """

    cart_id = serializers.UUIDField(write_only=True)
    delivery_address = serializers.CharField(required=False, allow_blank=True)
    # delivery_phone = PhoneNumberField(required=False, allow_blank=True)
    requires_delivery = serializers.BooleanField(default=False)

    class Meta:
        model = Order
        fields = (
            "cart_id",
            "pharmacy",
            "delivery_address",
            "delivery_phone",
            "delivery_notes",
            "requires_delivery",
            "delivery_fee",
        )
        read_only_fields = ("subtotal", "total_amount")


class DrugSerializer(serializers.ModelSerializer):
    class Meta:
        model = Drug
        fields = (
            "id",
            "image",
            "name",
            "category",
            "base_unit",
            "unit_price",
            "low_stock_threshold",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = DrugSupplier
        fields = (
            "id",
            "name",
            "contact_person",
            "phone_number",
            "email",
            "address",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id",)


class DrugBatchSerializer(serializers.ModelSerializer):
    supplier = SupplierSerializer(read_only=True)
    drug = DrugSerializer(read_only=True)

    class Meta:
        model = DrugBatch
        fields = (
            "id",
            "drug",
            "batch_number",
            "expiry_date",
            "supplier",
            "created_at",
        )
        read_only_fields = ("id",)


class DrugBatchCreateSerializer(serializers.ModelSerializer):

    def to_representation(self, instance):
        return DrugBatchSerializer(instance).data

    class Meta:
        model = DrugBatch
        fields = (
            "id",
            "drug",
            "batch_number",
            "expiry_date",
            "supplier",
            "created_at",
        )
        read_only_fields = ("id",)


class StockMovementSerializer(serializers.ModelSerializer):
    drug = DrugSerializer(read_only=True)
    batch = DrugBatchSerializer(read_only=True)

    class Meta:
        model = StockMovement
        fields = (
            "id",
            "drug",
            "batch",
            "quantity",
            "reason",
            "note",
            "created_at",
        )
        read_only_fields = ("id",)


class StockMovementCreateSerializer(serializers.ModelSerializer):
    def to_representation(self, instance):
        return StockMovementSerializer(instance).data

    class Meta:
        model = StockMovement
        fields = (
            "id",
            "drug",
            "batch",
            "quantity",
            "reason",
            "note",
            "created_at",
        )
        read_only_fields = ("id",)


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = (
            "id",
            "user",
            "order",
            "amount",
            "reference",
            "authorization_url",
            "status",
            "date_created",
        )


class InitiatePaymentSerializer(serializers.Serializer):
    order = serializers.UUIDField()

    def validate_order(self, value):
        if not Order.objects.filter(id=value):
            raise exceptions.GeneralException(detail="Order does not exist")
        return Order.objects.get(id=value)


class VerifyPaymentSerializer(serializers.Serializer):
    reference = serializers.CharField()

    def validate_reference(self, value):
        if not Payment.objects.filter(reference=value).exists():
            raise exceptions.GeneralException(detail="Payment reference nto found")
        return Payment.objects.filter(reference=value).first()


class PlaceOrderItemSerializer(serializers.Serializer):
    drug = serializers.UUIDField()
    quantity = serializers.IntegerField()

    def validate_drug(self, value):
        if not Drug.objects.filter(id=value):
            raise exceptions.GeneralException(detail="One or more drug does not exist")
        return value


class PlaceOrderSerializer(serializers.Serializer):
    items = serializers.ListField(child=PlaceOrderItemSerializer())
    address = serializers.UUIDField(required=False)
    delivery_method = serializers.ChoiceField(choices=["pickup", "delivery"])


class SettlementOrderSerializer(serializers.ModelSerializer):
    order_id = serializers.UUIDField(source="order.id", read_only=True)
    order_number = serializers.CharField(source="order.order_number", read_only=True)
    order_date = serializers.DateTimeField(source="order.created_at", read_only=True)
    customer = serializers.SerializerMethodField()
    delivery_method = serializers.CharField(
        source="order.delivery_method", read_only=True
    )
    payment_status = serializers.CharField(
        source="order.payment_status", read_only=True
    )
    status = serializers.CharField(source="order.status", read_only=True)

    def get_customer(self, obj):
        user = obj.order.user
        full_name = f"{user.first_name} {user.last_name}".strip()
        return full_name or user.username or user.email

    class Meta:
        model = SettlementOrder
        fields = (
            "id",
            "order_id",
            "order_number",
            "order_date",
            "customer",
            "delivery_method",
            "payment_status",
            "status",
            "amount",
        )


class SettlementListSerializer(serializers.ModelSerializer):
    order_count = serializers.SerializerMethodField()

    def get_order_count(self, obj):
        return obj.settlement_orders.count()

    class Meta:
        model = Settlement
        fields = (
            "id",
            "settlement_date",
            "status",
            "total_amount",
            "order_count",
            "paid_at",
            "created_at",
            "updated_at",
        )


class SettlementDetailSerializer(serializers.ModelSerializer):
    order_count = serializers.SerializerMethodField()
    orders = SettlementOrderSerializer(source="settlement_orders", many=True)

    def get_order_count(self, obj):
        return obj.settlement_orders.count()

    class Meta:
        model = Settlement
        fields = (
            "id",
            "settlement_date",
            "status",
            "total_amount",
            "order_count",
            "paid_at",
            "created_at",
            "updated_at",
            "orders",
        )


class CalculateSettlementsSerializer(serializers.Serializer):
    date = serializers.DateField()
