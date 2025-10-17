from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import PatientProfile


@admin.register(PatientProfile)
class PatientProfileAdmin(ModelAdmin):
    list_display = [
        "user",
        "first_name",
        "surname",
        "phone_number",
        "blood_type",
        "insurance_provider",
        "date_created",
    ]

    list_filter = [
        "blood_type",
        "gender",
        "date_created",
    ]

    search_fields = [
        "user__email",
        "first_name",
        "surname",
        "last_name",
        "phone_number",
        "emergency_contact_name",
        "insurance_provider",
    ]

    readonly_fields = ["date_created", "last_updated", "bmi"]
    ordering = ["-date_created"]
