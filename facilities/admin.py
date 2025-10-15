from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import Facility, FacilityProfile


@admin.register(Facility)
class FacilityAdmin(ModelAdmin):
    list_display = [
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
