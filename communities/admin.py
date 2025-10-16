from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import (
    Organization,
    OrganizationFiles,
    HealthProgramType,
    HealthProgram,
    ProgramIntervention,
    BulkInterventionUpload,
    SurveyType,
    Survey,
    SurveyQuestion,
    SurveyQuestionOption,
    SurveyResponse,
    SurveyResponseAnswers,
    BulkSurveyUpload,
)


@admin.register(Organization)
class OrganizationAdmin(ModelAdmin):
    list_display = [
        "user",
        "organization_name",
        "organization_type",
        "created_at",
    ]

    list_filter = [
        "organization_type",
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
                )
            },
        ),
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


@admin.register(OrganizationFiles)
class OrganizationFilesAdmin(ModelAdmin):
    list_display = [
        "file_name",
        "document_type",
        "file_type",
        "created_at",
    ]
    list_filter = [
        "document_type",
        "file_type",
        "created_at",
    ]
    search_fields = ["file_name", "document_type"]
    readonly_fields = ["created_at", "updated_at"]
    ordering = ["-created_at"]


@admin.register(HealthProgramType)
class HealthProgramTypeAdmin(ModelAdmin):
    list_display = [
        "name",
        "description",
        "default",
        "created_at",
    ]
    list_filter = [
        "default",
        "created_at",
    ]
    search_fields = ["name", "description"]
    readonly_fields = ["created_at", "updated_at"]
    ordering = ["name"]


@admin.register(SurveyType)
class SurveyTypeAdmin(ModelAdmin):
    list_display = [
        "name",
        "description",
        "default",
        "created_at",
    ]
    list_filter = [
        "default",
        "created_at",
    ]
    search_fields = ["name", "description"]
    readonly_fields = ["created_at", "updated_at"]
    ordering = ["name"]


@admin.register(Survey)
class SurveyAdmin(ModelAdmin):
    list_display = [
        "title",
        "survey_type",
        "active",
        "end_date",
        "date_created",
    ]
    list_filter = [
        "survey_type",
        "active",
        "end_date",
        "date_created",
    ]
    search_fields = ["title", "description"]
    readonly_fields = ["date_created", "last_updated"]
    ordering = ["-date_created"]


@admin.register(SurveyQuestion)
class SurveyQuestionAdmin(ModelAdmin):
    list_display = [
        "survey",
        "question",
        "question_type",
        "required",
        "date_created",
    ]
    list_filter = [
        "question_type",
        "required",
        "date_created",
    ]
    search_fields = ["question", "survey__title"]
    readonly_fields = ["date_created", "last_updated"]
    ordering = ["-date_created"]


@admin.register(SurveyQuestionOption)
class SurveyQuestionOptionAdmin(ModelAdmin):
    list_display = [
        "question",
        "option",
        "date_created",
    ]
    list_filter = [
        "date_created",
    ]
    search_fields = ["option", "question__question"]
    readonly_fields = ["date_created", "last_updated"]
    ordering = ["-date_created"]


@admin.register(SurveyResponse)
class SurveyResponseAdmin(ModelAdmin):
    list_display = [
        "survey",
        "phone_number",
        "date_created",
    ]
    list_filter = [
        "survey",
        "date_created",
    ]
    search_fields = ["phone_number", "survey__title"]
    readonly_fields = ["date_created", "last_updated"]
    ordering = ["-date_created"]


@admin.register(SurveyResponseAnswers)
class SurveyResponseAnswersAdmin(ModelAdmin):
    list_display = [
        "response",
        "question",
        "answer",
        "date_created",
    ]
    list_filter = [
        "date_created",
    ]
    search_fields = ["answer", "question__question", "response__phone_number"]
    readonly_fields = ["date_created", "last_updated"]
    ordering = ["-date_created"]
