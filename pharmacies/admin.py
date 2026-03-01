from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import (
    PharmacyProfile,
    Drug,
    DrugBatch,
    DrugSupplier,
    DrugCategory,
    StockMovement,
    Payment,
    Order,
)


@admin.register(PharmacyProfile)
class PharmacyProfileAdmin(ModelAdmin):
    list_display = [
        "user",
        "pharmacy_name",
        "district",
        "region",
        "delivery_available",
        "created_at",
    ]

    list_filter = [
        "license_expiry_date",
        "district",
        "region",
        "delivery_available",
        "created_at",
    ]

    search_fields = [
        "user__email",
        "pharmacy_name",
        "pharmacy_license",
        "license_expiry_date",
        "district",
        "region",
    ]

    readonly_fields = ["created_at", "updated_at"]
    ordering = ["-created_at"]


@admin.register(DrugCategory)
class DrugCategoryAdmin(ModelAdmin):
    list_display = [
        "name",
    ]
    search_fields = [
        "name",
    ]
    readonly_fields = ["created_at", "updated_at"]
    ordering = ["-created_at"]


@admin.register(Drug)
class DrugAdmin(ModelAdmin):
    list_display = [
        "name",
        "pharmacy",
        "category",
        "base_unit",
        "unit_price",
        "low_stock_threshold",
    ]
    search_fields = [
        "name",
    ]
    list_filter = [
        "category",
        "base_unit",
        "unit_price",
        "low_stock_threshold",
    ]
    readonly_fields = ["created_at", "updated_at"]
    ordering = ["-created_at"]


@admin.register(DrugSupplier)
class DrugSupplierAdmin(ModelAdmin):
    list_display = [
        "pharmacy",
        "name",
        "phone_number",
        "email",
        "address",
    ]
    search_fields = [
        "name",
    ]
    list_filter = [
        "pharmacy",
    ]
    readonly_fields = ["created_at", "updated_at"]
    ordering = ["-created_at"]


@admin.register(DrugBatch)
class DrugBatchAdmin(ModelAdmin):
    list_display = [
        "drug",
        "batch_number",
        "expiry_date",
        "supplier",
    ]
    search_fields = [
        "drug",
    ]
    list_filter = [
        "drug",
        "expiry_date",
        "supplier",
    ]
    readonly_fields = ["created_at"]
    ordering = ["-created_at"]


@admin.register(StockMovement)
class StockMovementAdmin(ModelAdmin):
    list_display = [
        "drug",
        "batch",
        "quantity",
        "reason",
    ]
    list_filter = [
        "batch",
        "quantity",
        "reason",
    ]
    readonly_fields = ["created_at"]
    ordering = ["-created_at"]


@admin.register(Payment)
class PaymentAdmin(ModelAdmin):
    list_display = [
        "user",
        "order",
        "amount",
        "reference",
        "status",
    ]
    list_filter = [
        "status",
    ]
    search_fields = [
        "user",
        "order",
        "reference",
    ]
    readonly_fields = ["date_created", "last_updated"]
    ordering = ["-date_created"]


@admin.register(Order)
class OrderAdmin(ModelAdmin):
    list_display = [
        "order_number",
        "user",
        "pharmacy",
        "status",
        "payment_status",
    ]
    list_filter = [
        "status",
        "payment_status",
    ]
    search_fields = [
        "user",
        "pharmacy",
    ]
    # readonly_fields = ["date_created", "last_updated"]
    # ordering = ["-date_created"]
