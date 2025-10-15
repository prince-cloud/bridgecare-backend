from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import ProfessionalProfile


@admin.register(ProfessionalProfile)
class ProfessionalProfileAdmin(ModelAdmin):
    list_display = [
        "user",
        "practice_type",
        "years_of_experience",
        "license_number",
        "license_expiry_date",
        "is_license_valid",
        "created_at",
    ]

    list_filter = [
        "practice_type",
        "years_of_experience",
        "license_issuing_body",
        "created_at",
    ]

    search_fields = [
        "user__email",
        "license_number",
        "practice_type",
    ]

    readonly_fields = ["created_at", "updated_at", "is_license_valid"]
    ordering = ["-created_at"]
