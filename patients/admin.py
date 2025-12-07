from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import (
    Allergy,
    Diagnosis,
    MedicalHistory,
    Notes,
    PatientProfile,
    PatientAccess,
    Prescription,
    Visitation,
    Vitals,
)


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


@admin.register(PatientAccess)
class PatientAccessAdmin(ModelAdmin):
    list_display = [
        "patient",
        "health_professional",
        "is_active",
        "created_at",
        "updated_at",
    ]
    list_filter = [
        "is_active",
    ]


@admin.register(Visitation)
class VisitationAdmin(ModelAdmin):
    list_display = [
        "patient",
        "title",
        "description",
        "date_created",
        "last_updated",
    ]
    list_filter = [
        "date_created",
    ]
    search_fields = [
        "patient__user__email",
        "title",
        "description",
    ]
    readonly_fields = ["date_created", "last_updated"]
    ordering = ["-date_created"]


@admin.register(Diagnosis)
class DiagnosisAdmin(ModelAdmin):
    list_display = [
        "visitation",
        "diagnosis",
        "date_created",
        "last_updated",
    ]
    list_filter = [
        "date_created",
    ]
    search_fields = [
        "visitation__patient__user__email",
        "visitation__title",
        "visitation__description",
        "diagnosis",
    ]
    readonly_fields = ["date_created", "last_updated"]
    ordering = ["-date_created"]


@admin.register(Vitals)
class VitalsAdmin(ModelAdmin):
    list_display = [
        "visitation",
        "blood_pressure",
        "temperature",
        "height",
        "weight",
        "date_created",
        "last_updated",
    ]
    list_filter = [
        "date_created",
    ]
    search_fields = [
        "visitation__patient__user__email",
        "visitation__title",
        "visitation__description",
    ]
    readonly_fields = ["date_created", "last_updated"]
    ordering = ["-date_created"]


@admin.register(Prescription)
class PrescriptionAdmin(ModelAdmin):
    list_display = [
        "visitation",
        "medication",
        "dosage",
        "frequency",
        "duration",
        "instructions",
    ]
    readonly_fields = ["date_created", "last_updated"]
    ordering = ["-date_created"]


@admin.register(Allergy)
class AllergyAdmin(ModelAdmin):
    list_display = [
        "patient",
        "allergy",
        "allergy_severity",
        "date_created",
        "last_updated",
    ]
    readonly_fields = ["date_created", "last_updated"]
    ordering = ["-date_created"]


@admin.register(Notes)
class NotesAdmin(ModelAdmin):
    list_display = [
        "visitation",
        "note",
        "date_created",
        "last_updated",
    ]
    readonly_fields = ["date_created", "last_updated"]
    ordering = ["-date_created"]


@admin.register(MedicalHistory)
class MedicalHistoryAdmin(ModelAdmin):
    list_display = [
        "patient",
        "history_type",
        "name",
        "date_created",
        "last_updated",
    ]
    readonly_fields = ["date_created", "last_updated"]
    ordering = ["-date_created"]
