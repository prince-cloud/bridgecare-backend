from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import PartnerProfile, Subsidy, ProgramPartnershipRequest, ProgramMonitor


@admin.register(PartnerProfile)
class PartnerProfileAdmin(ModelAdmin):
    list_display = [
        "organization_name",
        "organization_type",
        "partnership_type",
        "is_verified",
        "partnership_status",
        "created_at",
    ]
    list_filter = [
        "organization_type",
        "partnership_type",
        "partnership_status",
        "is_verified",
        "created_at",
    ]
    search_fields = ["user__email", "organization_name", "registration_number"]
    readonly_fields = ["slug", "created_at", "updated_at"]
    ordering = ["-created_at"]


@admin.register(Subsidy)
class SubsidyAdmin(ModelAdmin):
    list_display = ["name", "partner", "subsidy_type", "total_budget", "budget_used", "status", "start_date"]
    list_filter = ["subsidy_type", "status"]
    search_fields = ["name", "partner__organization_name"]
    readonly_fields = ["created_at", "updated_at"]
    ordering = ["-created_at"]


@admin.register(ProgramPartnershipRequest)
class ProgramPartnershipRequestAdmin(ModelAdmin):
    list_display = ["partner", "program", "direction", "status", "report_frequency", "created_at"]
    list_filter = ["status", "direction", "report_frequency"]
    search_fields = ["partner__organization_name", "program__program_name"]
    readonly_fields = ["created_at", "updated_at", "reviewed_at"]
    ordering = ["-created_at"]


@admin.register(ProgramMonitor)
class ProgramMonitorAdmin(ModelAdmin):
    list_display = ["partner", "program", "report_frequency", "is_active", "created_at"]
    list_filter = ["is_active", "report_frequency"]
    search_fields = ["partner__organization_name", "program__program_name"]
    readonly_fields = ["created_at"]
    ordering = ["-created_at"]
