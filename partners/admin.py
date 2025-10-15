from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import PartnerProfile


@admin.register(PartnerProfile)
class PartnerProfileAdmin(ModelAdmin):
    list_display = [
        "user",
        "organization_name",
        "organization_type",
        "partnership_type",
        "partnership_status",
        "created_at",
    ]

    list_filter = [
        "organization_type",
        "partnership_type",
        "partnership_status",
        "api_access_level",
        "created_at",
    ]

    search_fields = [
        "user__email",
        "organization_name",
        "organization_type",
    ]

    readonly_fields = ["created_at", "updated_at"]
    ordering = ["-created_at"]
