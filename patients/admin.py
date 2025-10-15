from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import PatientProfile


@admin.register(PatientProfile)
class PatientProfileAdmin(ModelAdmin):
    list_display = [
        "user",
        "blood_type",
        "preferred_consultation_type",
        "preferred_payment_method",
        "insurance_provider",
        "created_at",
    ]

    list_filter = [
        "blood_type",
        "preferred_consultation_type",
        "preferred_payment_method",
        "preferred_language",
        "created_at",
    ]

    search_fields = [
        "user__email",
        "emergency_contact_name",
        "insurance_provider",
    ]

    readonly_fields = ["created_at", "updated_at", "bmi"]
    ordering = ["-created_at"]
