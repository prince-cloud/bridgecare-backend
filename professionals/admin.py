from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import (
    ProfessionalProfile,
    Profession,
    Specialization,
    LicenceIssueAuthority,
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
