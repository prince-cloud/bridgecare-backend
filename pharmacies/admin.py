from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import PharmacyProfile


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
