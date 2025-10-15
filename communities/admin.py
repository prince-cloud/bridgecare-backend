from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import (
    CommunityProfile,
    HealthProgram,
    ProgramIntervention,
    BulkInterventionUpload,
    ProgramSchedule,
    HealthSurvey,
    SurveyResponse,
    BulkSurveyUpload,
    ProgramReport,
)


@admin.register(CommunityProfile)
class CommunityProfileAdmin(ModelAdmin):
    list_display = [
        "user",
        "organization_name",
        "organization_type",
        "coordinator_level",
        "volunteer_status",
        "created_at",
    ]

    list_filter = [
        "organization_type",
        "coordinator_level",
        "volunteer_status",
        "created_at",
    ]

    search_fields = [
        "user__email",
        "organization_name",
        "organization_type",
    ]

    readonly_fields = ["created_at", "updated_at"]

    ordering = ["-created_at"]

    fieldsets = (
        ("User", {"fields": ("user",)}),
        (
            "Organization Details",
            {
                "fields": (
                    "organization_name",
                    "organization_type",
                    "volunteer_status",
                    "coordinator_level",
                )
            },
        ),
        ("Areas of Focus", {"fields": ("areas_of_focus",)}),
        (
            "Contact Information",
            {
                "fields": (
                    "organization_phone",
                    "organization_email",
                    "organization_address",
                )
            },
        ),
        ("Programs & Certifications", {"fields": ("active_programs", "certifications")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )


@admin.register(HealthProgram)
class HealthProgramAdmin(ModelAdmin):
    list_display = [
        "program_name",
        "organization",
        "program_type",
        "start_date",
        "end_date",
        "status",
        "district",
        "region",
        "target_participants",
        "actual_participants",
        "participation_rate",
        "created_at",
    ]

    list_filter = [
        "program_type",
        "status",
        "district",
        "region",
        "organization",
        "start_date",
        "created_at",
    ]

    search_fields = [
        "program_name",
        "description",
        "location_name",
        "lead_organizer",
        "district",
        "region",
        "organization__organization_name",
        "organization__organization_type",
    ]

    readonly_fields = ["created_at", "updated_at", "participation_rate"]

    ordering = ["-start_date"]

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "program_name",
                    "program_type",
                    "program_type_custom",
                    "description",
                )
            },
        ),
        ("Schedule", {"fields": ("start_date", "end_date")}),
        (
            "Location",
            {
                "fields": (
                    "location_name",
                    "district",
                    "region",
                    "latitude",
                    "longitude",
                    "location_details",
                )
            },
        ),
        (
            "Participants",
            {
                "fields": (
                    "target_participants",
                    "actual_participants",
                    "participation_rate",
                )
            },
        ),
        ("Interventions", {"fields": ("interventions_planned",)}),
        (
            "Organization",
            {
                "fields": (
                    "organization",
                    "created_by",
                    "lead_organizer",
                    "lead_organizer_contact",
                    "partner_organizations",
                    "funding_source",
                    "team_members",
                )
            },
        ),
        ("Status", {"fields": ("status",)}),
        ("Sync", {"fields": ("is_synced", "offline_id")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )


@admin.register(ProgramIntervention)
class ProgramInterventionAdmin(ModelAdmin):
    list_display = [
        "intervention_name",
        "program",
        "intervention_type",
        "participant_name",
        "participant_age",
        "participant_gender",
        "referral_needed",
        "synced_to_ehr",
        "documented_at",
    ]

    list_filter = [
        "intervention_type",
        "participant_gender",
        "referral_needed",
        "synced_to_ehr",
        "follow_up_required",
        "documented_at",
    ]

    search_fields = [
        "participant_name",
        "participant_id",
        "intervention_name",
        "diagnosis",
        "notes",
    ]

    readonly_fields = ["documented_at", "updated_at"]

    ordering = ["-documented_at"]


@admin.register(BulkInterventionUpload)
class BulkInterventionUploadAdmin(ModelAdmin):
    list_display = [
        "file_name",
        "program",
        "uploaded_by",
        "status",
        "total_rows",
        "successful_rows",
        "failed_rows",
        "uploaded_at",
    ]

    list_filter = ["status", "uploaded_at"]

    search_fields = ["file_name", "program__program_name"]

    readonly_fields = [
        "uploaded_at",
        "processed_at",
        "total_rows",
        "processed_rows",
        "successful_rows",
        "failed_rows",
        "errors",
        "processing_log",
    ]

    ordering = ["-uploaded_at"]


@admin.register(ProgramSchedule)
class ProgramScheduleAdmin(ModelAdmin):
    list_display = [
        "program",
        "scheduled_date",
        "start_time",
        "end_time",
        "location_name",
        "is_confirmed",
        "transportation_arranged",
        "created_at",
    ]

    list_filter = [
        "is_confirmed",
        "transportation_arranged",
        "accommodation_needed",
        "scheduled_date",
    ]

    search_fields = ["program__program_name", "location_name", "notes"]

    readonly_fields = ["created_at", "updated_at"]

    ordering = ["scheduled_date", "start_time"]


@admin.register(HealthSurvey)
class HealthSurveyAdmin(ModelAdmin):
    list_display = [
        "title",
        "survey_type",
        "program",
        "status",
        "target_count",
        "actual_responses",
        "response_rate",
        "start_date",
        "end_date",
        "created_at",
    ]

    list_filter = [
        "survey_type",
        "status",
        "is_anonymous",
        "requires_authentication",
        "start_date",
        "created_at",
    ]

    search_fields = ["title", "description", "target_audience"]

    readonly_fields = ["created_at", "updated_at", "actual_responses", "response_rate"]

    ordering = ["-created_at"]

    fieldsets = (
        ("Basic Information", {"fields": ("title", "description", "survey_type")}),
        ("Association", {"fields": ("program",)}),
        ("Survey Structure", {"fields": ("questions",)}),
        (
            "Target Audience",
            {"fields": ("target_audience", "target_count", "actual_responses")},
        ),
        (
            "Settings",
            {
                "fields": (
                    "is_anonymous",
                    "allow_multiple_responses",
                    "requires_authentication",
                )
            },
        ),
        (
            "Language",
            {"fields": ("primary_language", "available_languages")},
        ),
        ("Status & Timing", {"fields": ("status", "start_date", "end_date")}),
        ("Metadata", {"fields": ("created_by", "supports_offline")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )


@admin.register(SurveyResponse)
class SurveyResponseAdmin(ModelAdmin):
    list_display = [
        "survey",
        "respondent_name",
        "respondent_age",
        "respondent_gender",
        "respondent_location",
        "language_used",
        "submitted_at",
    ]

    list_filter = [
        "survey",
        "respondent_gender",
        "language_used",
        "submitted_at",
    ]

    search_fields = [
        "respondent_name",
        "respondent_location",
        "survey__title",
    ]

    readonly_fields = ["submitted_at", "updated_at", "synced_at"]

    ordering = ["-submitted_at"]


@admin.register(BulkSurveyUpload)
class BulkSurveyUploadAdmin(ModelAdmin):
    list_display = [
        "file_name",
        "survey",
        "uploaded_by",
        "status",
        "total_rows",
        "successful_rows",
        "failed_rows",
        "uploaded_at",
    ]

    list_filter = ["status", "uploaded_at"]

    search_fields = ["file_name", "survey__title"]

    readonly_fields = [
        "uploaded_at",
        "processed_at",
        "total_rows",
        "processed_rows",
        "successful_rows",
        "failed_rows",
        "errors",
        "processing_log",
    ]

    ordering = ["-uploaded_at"]


@admin.register(ProgramReport)
class ProgramReportAdmin(ModelAdmin):
    list_display = [
        "title",
        "program",
        "report_type",
        "start_date",
        "end_date",
        "generated_by",
        "generated_at",
    ]

    list_filter = ["report_type", "generated_at"]

    search_fields = ["title", "description", "program__program_name"]

    readonly_fields = ["generated_at", "updated_at"]

    ordering = ["-generated_at"]

    fieldsets = (
        ("Basic Information", {"fields": ("program", "report_type", "title", "description")}),
        ("Report Data", {"fields": ("report_data", "charts")}),
        ("Period", {"fields": ("start_date", "end_date")}),
        ("Report File", {"fields": ("report_file",)}),
        ("Metadata", {"fields": ("generated_by", "generated_at", "updated_at")}),
    )
