from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import (
    ProfessionalProfile,
    Profession,
    Specialization,
    LicenceIssueAuthority,
    AvailabilityBlock,
    BreakPeriod,
    Appointment,
)


@admin.register(ProfessionalProfile)
class ProfessionalProfileAdmin(ModelAdmin):
    list_display = [
        "id",
        "user",
        "profession",
        "specialization",
        "education_status",
        "facility_affiliation",
        "is_active",
        "created_at",
    ]

    list_filter = [
        "profession",
        "specialization",
        "education_status",
        "facility_affiliation",
        "is_active",
    ]

    search_fields = []


@admin.register(Profession)
class ProfessionAdmin(ModelAdmin):
    list_display = [
        "id",
        "name",
        "description",
        "is_active",
    ]


@admin.register(Specialization)
class SpecializationAdmin(ModelAdmin):
    list_display = [
        "id",
        "name",
        "description",
        "is_active",
    ]


@admin.register(LicenceIssueAuthority)
class LicenceIssueAuthorityAdmin(ModelAdmin):
    list_display = [
        "id",
        "name",
        "description",
    ]


@admin.register(AvailabilityBlock)
class AvailabilityBlockAdmin(ModelAdmin):
    list_display = [
        "id",
        "provider",
        "day_of_week",
        "start_time",
        "end_time",
        "slot_duration",
        "created_at",
    ]
    list_filter = [
        "provider",
        "day_of_week",
        "slot_duration",
    ]
    search_fields = [
        "provider__user__email",
        "provider__user__first_name",
        "provider__user__last_name",
    ]


@admin.register(BreakPeriod)
class BreakPeriodAdmin(ModelAdmin):
    list_display = [
        "id",
        "availability",
        "break_start",
        "break_end",
        "created_at",
    ]
    list_filter = [
        "availability__provider",
        "availability__day_of_week",
    ]
    search_fields = [
        "availability__provider__user__email",
        "availability__provider__user__first_name",
        "availability__provider__user__last_name",
    ]


@admin.register(Appointment)
class AppointmentAdmin(ModelAdmin):
    list_display = [
        "id",
        "provider",
        "patient",
        "date",
        "start_time",
        "end_time",
        "appointment_type",
        "telehealth_mode",
        "visitation_type",
        "visitation_location",
        "status",
        "created_at",
    ]
    list_filter = [
        "provider",
        "date",
        "appointment_type",
        "telehealth_mode",
        "visitation_type",
        "visitation_location",
        "status",
    ]
    search_fields = [
        "provider__user__email",
        "provider__user__first_name",
        "provider__user__last_name",
        "patient__user__email",
        "patient__first_name",
        "patient__last_name",
    ]
