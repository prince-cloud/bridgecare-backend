from rest_framework import serializers
from .models import (
    CommunityProfile,
    HealthProgram,
    ProgramIntervention,
    BulkInterventionUpload,
    HealthSurvey,
    SurveyResponse,
    BulkSurveyUpload,
    ProgramReport,
)
from accounts.serializers import UserSerializer


class CommunityProfileSerializer(serializers.ModelSerializer):
    """
    Community profile serializer
    """

    user = UserSerializer(read_only=True)
    programs_count = serializers.SerializerMethodField()

    class Meta:
        model = CommunityProfile
        fields = (
            "id",
            "user",
            "organization_name",
            "organization_type",
            "volunteer_status",
            "coordinator_level",
            "areas_of_focus",
            "organization_phone",
            "organization_email",
            "organization_address",
            "active_programs",
            "certifications",
            "programs_count",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def get_programs_count(self, obj):
        return obj.health_programs.count()


class HealthProgramSerializer(serializers.ModelSerializer):
    """
    Serializer for health programs
    """

    program_type_display = serializers.CharField(
        source="get_program_type_display", read_only=True
    )
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    organization_name = serializers.CharField(
        source="organization.organization_name", read_only=True
    )
    organization_type = serializers.CharField(
        source="organization.organization_type", read_only=True
    )
    created_by_name = serializers.SerializerMethodField()
    is_active = serializers.BooleanField(read_only=True)
    participation_rate = serializers.FloatField(read_only=True)
    interventions_count = serializers.SerializerMethodField()
    surveys_count = serializers.SerializerMethodField()

    class Meta:
        model = HealthProgram
        fields = [
            "id",
            "program_name",
            "program_type",
            "program_type_display",
            "program_type_custom",
            "description",
            "start_date",
            "end_date",
            "location_name",
            "district",
            "region",
            "latitude",
            "longitude",
            "location_details",
            "target_participants",
            "actual_participants",
            "participation_rate",
            "interventions_planned",
            "organization",
            "organization_name",
            "organization_type",
            "created_by",
            "created_by_name",
            "lead_organizer",
            "lead_organizer_contact",
            "partner_organizations",
            "funding_source",
            "status",
            "status_display",
            "team_members",
            "is_active",
            "interventions_count",
            "surveys_count",
            "is_synced",
            "locum_needs",
            "equipment_needs",
            "equipment_list",
            "offline_id",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "is_synced"]

    def get_created_by_name(self, obj):
        if obj.created_by:
            return f"{obj.created_by.first_name} {obj.created_by.last_name}"
        return None

    def get_interventions_count(self, obj):
        return obj.interventions.count()

    def get_surveys_count(self, obj):
        return obj.surveys.count()


class ProgramInterventionSerializer(serializers.ModelSerializer):
    """
    Serializer for program interventions
    """

    intervention_type_display = serializers.CharField(
        source="get_intervention_type_display", read_only=True
    )
    participant_gender_display = serializers.CharField(
        source="get_participant_gender_display", read_only=True
    )
    documented_by_name = serializers.SerializerMethodField()
    program_name = serializers.CharField(source="program.program_name", read_only=True)
    referral_facility_name = serializers.CharField(
        source="referral_facility.name", read_only=True
    )

    class Meta:
        model = ProgramIntervention
        fields = [
            "id",
            "program",
            "program_name",
            "intervention_type",
            "intervention_type_display",
            "intervention_name",
            "description",
            "participant_id",
            "participant_name",
            "participant_age",
            "participant_gender",
            "participant_gender_display",
            "participant_phone",
            "blood_pressure",
            "temperature",
            "pulse",
            "weight",
            "height",
            "test_results",
            "vaccine_administered",
            "vaccine_dose_number",
            "vaccine_batch_number",
            "vaccination_date",
            "symptoms",
            "diagnosis",
            "treatment_given",
            "referral_needed",
            "referral_facility",
            "referral_facility_name",
            "referral_notes",
            "notes",
            "follow_up_required",
            "follow_up_date",
            "documented_by",
            "documented_by_name",
            "synced_to_ehr",
            "ehr_record_id",
            "offline_id",
            "documented_at",
            "updated_at",
        ]
        read_only_fields = ["id", "documented_at", "updated_at"]

    def get_documented_by_name(self, obj):
        if obj.documented_by:
            return f"{obj.documented_by.first_name} {obj.documented_by.last_name}"
        return None


class BulkInterventionUploadSerializer(serializers.ModelSerializer):
    """
    Serializer for bulk intervention uploads
    """

    status_display = serializers.CharField(source="get_status_display", read_only=True)
    uploaded_by_name = serializers.SerializerMethodField()
    program_name = serializers.CharField(source="program.program_name", read_only=True)
    progress_percentage = serializers.SerializerMethodField()

    class Meta:
        model = BulkInterventionUpload
        fields = [
            "id",
            "program",
            "program_name",
            "uploaded_by",
            "uploaded_by_name",
            "file",
            "file_name",
            "status",
            "status_display",
            "total_rows",
            "processed_rows",
            "successful_rows",
            "failed_rows",
            "progress_percentage",
            "errors",
            "processing_log",
            "uploaded_at",
            "processed_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "total_rows",
            "processed_rows",
            "successful_rows",
            "failed_rows",
            "errors",
            "processing_log",
            "uploaded_at",
            "processed_at",
        ]

    def get_uploaded_by_name(self, obj):
        if obj.uploaded_by:
            return f"{obj.uploaded_by.first_name} {obj.uploaded_by.last_name}"
        return None

    def get_progress_percentage(self, obj):
        if obj.total_rows > 0:
            return round((obj.processed_rows / obj.total_rows) * 100, 2)
        return 0


class HealthSurveySerializer(serializers.ModelSerializer):
    """
    Serializer for health surveys
    """

    survey_type_display = serializers.CharField(
        source="get_survey_type_display", read_only=True
    )
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    created_by_name = serializers.SerializerMethodField()
    program_name = serializers.CharField(
        source="program.program_name", read_only=True, allow_null=True
    )
    response_rate = serializers.FloatField(read_only=True)
    responses_count = serializers.SerializerMethodField()

    class Meta:
        model = HealthSurvey
        fields = [
            "id",
            "title",
            "description",
            "survey_type",
            "survey_type_display",
            "program",
            "program_name",
            "questions",
            "target_audience",
            "target_count",
            "actual_responses",
            "response_rate",
            "responses_count",
            "is_anonymous",
            "allow_multiple_responses",
            "requires_authentication",
            "primary_language",
            "available_languages",
            "status",
            "status_display",
            "start_date",
            "end_date",
            "created_by",
            "created_by_name",
            "supports_offline",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "actual_responses", "created_at", "updated_at"]

    def get_created_by_name(self, obj):
        if obj.created_by:
            return f"{obj.created_by.first_name} {obj.created_by.last_name}"
        return None

    def get_responses_count(self, obj):
        return obj.responses.count()


class SurveyResponseSerializer(serializers.ModelSerializer):
    """
    Serializer for survey responses
    """

    survey_title = serializers.CharField(source="survey.title", read_only=True)
    respondent_name_display = serializers.SerializerMethodField()

    class Meta:
        model = SurveyResponse
        fields = [
            "id",
            "survey",
            "survey_title",
            "respondent",
            "respondent_name",
            "respondent_name_display",
            "respondent_age",
            "respondent_gender",
            "respondent_location",
            "answers",
            "language_used",
            "submitted_at",
            "updated_at",
            "ip_address",
            "offline_id",
            "synced_at",
        ]
        read_only_fields = ["id", "submitted_at", "updated_at", "synced_at"]

    def get_respondent_name_display(self, obj):
        if obj.respondent:
            return f"{obj.respondent.first_name} {obj.respondent.last_name}"
        return obj.respondent_name or "Anonymous"


class BulkSurveyUploadSerializer(serializers.ModelSerializer):
    """
    Serializer for bulk survey uploads
    """

    status_display = serializers.CharField(source="get_status_display", read_only=True)
    uploaded_by_name = serializers.SerializerMethodField()
    survey_title = serializers.CharField(source="survey.title", read_only=True)
    progress_percentage = serializers.SerializerMethodField()

    class Meta:
        model = BulkSurveyUpload
        fields = [
            "id",
            "survey",
            "survey_title",
            "uploaded_by",
            "uploaded_by_name",
            "file",
            "file_name",
            "status",
            "status_display",
            "total_rows",
            "processed_rows",
            "successful_rows",
            "failed_rows",
            "progress_percentage",
            "errors",
            "processing_log",
            "uploaded_at",
            "processed_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "total_rows",
            "processed_rows",
            "successful_rows",
            "failed_rows",
            "errors",
            "processing_log",
            "uploaded_at",
            "processed_at",
        ]

    def get_uploaded_by_name(self, obj):
        if obj.uploaded_by:
            return f"{obj.uploaded_by.first_name} {obj.uploaded_by.last_name}"
        return None

    def get_progress_percentage(self, obj):
        if obj.total_rows > 0:
            return round((obj.processed_rows / obj.total_rows) * 100, 2)
        return 0


class ProgramReportSerializer(serializers.ModelSerializer):
    """
    Serializer for program reports
    """

    report_type_display = serializers.CharField(
        source="get_report_type_display", read_only=True
    )
    generated_by_name = serializers.SerializerMethodField()
    program_name = serializers.CharField(source="program.program_name", read_only=True)

    class Meta:
        model = ProgramReport
        fields = [
            "id",
            "program",
            "program_name",
            "report_type",
            "report_type_display",
            "title",
            "description",
            "report_data",
            "charts",
            "start_date",
            "end_date",
            "report_file",
            "generated_by",
            "generated_by_name",
            "generated_at",
            "updated_at",
        ]
        read_only_fields = ["id", "generated_at", "updated_at"]

    def get_generated_by_name(self, obj):
        if obj.generated_by:
            return f"{obj.generated_by.first_name} {obj.generated_by.last_name}"
        return None


# Summary/Statistics Serializers
class ProgramStatisticsSerializer(serializers.Serializer):
    """
    Serializer for program statistics and analytics
    """

    total_programs = serializers.IntegerField()
    active_programs = serializers.IntegerField()
    completed_programs = serializers.IntegerField()
    total_participants = serializers.IntegerField()
    total_interventions = serializers.IntegerField()
    total_surveys = serializers.IntegerField()
    programs_by_type = serializers.DictField()
    programs_by_region = serializers.DictField()
    monthly_trends = serializers.ListField()
