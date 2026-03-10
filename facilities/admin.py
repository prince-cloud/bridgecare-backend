from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import Facility, FacilityProfile, Locum, FacilityStaff


@admin.register(Facility)
class FacilityAdmin(ModelAdmin):
    list_display = [
        "id",
        "name",
        "facility_code",
        "facility_type",
        "district",
        "region",
        "is_active",
        "created_at",
    ]

    list_filter = [
        "facility_type",
        "district",
        "region",
        "is_active",
        "created_at",
    ]

    search_fields = [
        "name",
        "facility_code",
        "district",
        "region",
    ]

    readonly_fields = ["created_at", "updated_at"]
    ordering = ["name"]


@admin.register(FacilityProfile)
class FacilityProfileAdmin(ModelAdmin):
    list_display = [
        "id",
        "user",
        "facility",
        "department",
        "position",
        "employment_type",
        "created_at",
    ]

    list_filter = [
        "facility",
        "department",
        "position",
        "employment_type",
        "can_prescribe",
        "created_at",
    ]

    search_fields = [
        "user__email",
        "facility__name",
        "employee_id",
        "position",
    ]

    readonly_fields = ["created_at", "updated_at"]
    ordering = ["-created_at"]


@admin.register(Locum)
class LocumAdmin(ModelAdmin):
    list_display = [
        "full_name",
        "profession",
        "phone_number",
        "is_available",
        "region",
        "district",
    ]
    list_filter = ["profession", "is_available", "region", "district"]
    search_fields = ["full_name", "email", "license_number"]
    readonly_fields = ["created_at", "updated_at"]
    ordering = ["-created_at"]


@admin.register(FacilityStaff)
class FacilityStaffAdmin(ModelAdmin):
    list_display = [
        "facility",
        "full_name",
        "profession",
        "position",
        "department",
        "is_active",
    ]
    list_filter = [
        "is_active",
        "profession",
        "facility",
        "department",
    ]
    search_fields = [
        "facility__name",
        "full_name",
        "employee_id",
        "position",
        "email",
    ]
    readonly_fields = ["created_at", "updated_at"]
    ordering = ["-created_at"]
