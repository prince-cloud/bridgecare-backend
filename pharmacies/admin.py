from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import PharmacyProfile


@admin.register(PharmacyProfile)
class PharmacyProfileAdmin(ModelAdmin):
    list_display = [
        "user",
        "pharmacy_name",
        "pharmacy_type",
        "district",
        "region",
        "delivery_available",
        "created_at",
    ]

    list_filter = [
        "pharmacy_type",
        "district",
        "region",
        "delivery_available",
        "created_at",
    ]

    search_fields = [
        "user__email",
        "pharmacy_name",
        "pharmacy_license",
        "district",
        "region",
    ]

    readonly_fields = ["created_at", "updated_at"]
    ordering = ["-created_at"]
