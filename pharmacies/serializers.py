from rest_framework import serializers
from .models import (
    PharmacyProfile,
    Drug,
    DrugBatch,
    DrugSupplier,
    DrugCategory,
)
from accounts.serializers import UserSerializer
from django.utils import timezone


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
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class DrugCategorySerializer(serializers.ModelSerializer):
    """
    Drug category serializer
    """

    class Meta:
        model = DrugCategory
        fields = ("id", "name")
        read_only_fields = ("id",)


class DrugSupplierSerializer(serializers.ModelSerializer):

    class Meta:
        model = DrugSupplier
        fields = ("id", "name", "phone_number", "email", "address")
        read_only_fields = ("id",)


class DrugBatchSerializer(serializers.ModelSerializer):
    """
    Drug batch serializer
    """

    class Meta:
        model = DrugBatch
        fields = ("id", "batch_number", "expiry_date", "supplier")
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
