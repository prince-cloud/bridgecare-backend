from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import (
    Organization,
    OrganizationFiles,
    HealthProgramType,
    HealthProgram,
    ProgramInterventionType,
    ProgramIntervention,
    InterventionField,
    InterventionFieldOption,
    InterventionResponse,
    InterventionResponseValue,
    BulkInterventionUpload,
    SurveyType,
    Survey,
    SurveyQuestion,
    SurveyQuestionOption,
    SurveyResponse,
    SurveyResponseAnswers,
    BulkSurveyUpload,
    LocumJobRole,
    LocumJob,
    HealthProgramPartners,
    LocumJobApplication,
    Staff,
)


@admin.register(Staff)
class StaffAdmin(ModelAdmin):
    list_display = [
        "id",
        "organization",
        "first_name",
        "last_name",
        "email",
        "account_type",
        "phone_number",
        "created_at",
    ]
    list_filter = ["organization", "created_at"]


@admin.register(Organization)
class OrganizationAdmin(ModelAdmin):
    list_display = [
        "id",
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
        "district",
        "region",
        "organization__organization_name",
        "organization__organization_type",
    ]


@admin.register(ProgramIntervention)
class ProgramInterventionAdmin(ModelAdmin):
    list_display = [
        "id",
        "program",
        "intervention_type",
        "created_at",
    ]

    list_filter = [
        "intervention_type",
        "created_at",
    ]

    search_fields = [
        "program__program_name",
        "intervention_type__name",
    ]

    readonly_fields = ["created_at", "updated_at"]

    ordering = ["-created_at"]


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
        "organization",
        "file_name",
        "document_type",
        "file_type",
        "created_at",
    ]
    list_filter = [
        "organization",
        "document_type",
        "file_type",
        "created_at",
    ]
    search_fields = ["file_name", "document_type", "organization__organization_name"]
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


@admin.register(ProgramInterventionType)
class ProgramInterventionTypeAdmin(ModelAdmin):
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


@admin.register(InterventionField)
class InterventionFieldAdmin(ModelAdmin):
    list_display = [
        "intervention",
        "name",
        "field_type",
        "required",
        "date_created",
    ]
    list_filter = [
        "field_type",
        "required",
        "date_created",
    ]
    search_fields = ["name", "intervention__intervention_type__name"]
    readonly_fields = ["date_created", "last_updated"]
    ordering = ["-date_created"]


@admin.register(InterventionFieldOption)
class InterventionFieldOptionAdmin(ModelAdmin):
    list_display = [
        "field",
        "option",
        "date_created",
    ]
    list_filter = [
        "date_created",
    ]
    search_fields = ["option", "field__name"]
    readonly_fields = ["date_created", "last_updated"]
    ordering = ["-date_created"]


@admin.register(InterventionResponse)
class InterventionResponseAdmin(ModelAdmin):
    list_display = [
        "id",
        "intervention",
        "participant_id",
        "patient_record",
        "date_created",
    ]
    list_filter = [
        "intervention",
        "date_created",
    ]
    search_fields = [
        "participant_id",
        "patient_record__first_name",
        "intervention__intervention_type__name",
    ]
    readonly_fields = ["date_created", "last_updated"]
    ordering = ["-date_created"]


@admin.register(InterventionResponseValue)
class InterventionResponseValueAdmin(ModelAdmin):
    list_display = [
        "id",
        "response",
        "field",
        "value",
        "date_created",
    ]
    list_filter = [
        "field__field_type",
        "date_created",
    ]
    search_fields = ["value", "field__name", "participant__participant_id"]
    readonly_fields = ["date_created", "last_updated"]
    ordering = ["-date_created"]


@admin.register(LocumJobRole)
class LocumJobRoleAdmin(ModelAdmin):
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


@admin.register(LocumJob)
class LocumJobAdmin(ModelAdmin):
    list_display = [
        "title",
        "role",
        "organization",
        "location",
        "renumeration",
        "renumeration_frequency",
        "is_active",
        "approved",
        "date_created",
    ]
    list_filter = [
        "role",
        "organization",
        "is_active",
        "approved",
        "renumeration_frequency",
        "date_created",
    ]
    search_fields = [
        "title",
        "description",
        "location",
        "organization__organization_name",
        "role__name",
    ]
    readonly_fields = ["date_created", "last_updated"]
    ordering = ["-date_created"]


@admin.register(HealthProgramPartners)
class HealthProgramPartnersAdmin(ModelAdmin):
    list_display = [
        "name",
        "url",
        "has_logo",
        "date_created",
    ]
    list_filter = [
        "date_created",
    ]
    search_fields = ["name", "url"]
    readonly_fields = ["date_created", "last_updated"]
    ordering = ["name"]

    def has_logo(self, obj):
        return bool(obj.logo)

    has_logo.boolean = True
    has_logo.short_description = "Has Logo"


@admin.register(LocumJobApplication)
class LocumJobApplicationAdmin(ModelAdmin):
    list_display = [
        "job",
        "applicant",
        "applied_at",
        "status",
    ]
    list_filter = [
        "job",
        "applied_at",
        "status",
    ]
    search_fields = ["job__title", "applicant__email"]
    readonly_fields = ["applied_at"]
    ordering = ["-applied_at"]
