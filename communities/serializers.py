from rest_framework import serializers
from .models import (
    Organization,
    HealthProgramType,
    HealthProgram,
    ProgramInterventionType,
    ProgramIntervention,
    InterventionField,
    InterventionFieldOption,
    InterventionResponse,
    InterventionResponseValue,
    BulkInterventionUpload,
    Survey,
    SurveyType,
    SurveyQuestionOption,
    SurveyQuestion,
    SurveyResponse,
    SurveyResponseAnswers,
    BulkSurveyUpload,
    OrganizationFiles,
)
from accounts.serializers import UserSerializer
from helpers import exceptions


class OrganizationFilesSerializer(serializers.ModelSerializer):
    """
    Community documentation serializer
    """

    class Meta:
        model = OrganizationFiles
        fields = [
            "id",
            "document_type",
            "file",
            "file_type",
            "file_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "file_type", "file_name", "updated_at"]


class OrganizationSerializer(serializers.ModelSerializer):
    """
    Organization serializer
    """

    user = UserSerializer(read_only=True)
    files = OrganizationFilesSerializer(many=True, read_only=True)

    class Meta:
        model = Organization
        fields = (
            "id",
            "user",
            "organization_name",
            "organization_type",
            "organization_phone",
            "organization_email",
            "organization_address",
            "orgnaization_logo",
            "verified",
            "files",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class OrganizationCreateFilesSerializer(serializers.Serializer):
    file = serializers.FileField(required=True)
    document_type = serializers.CharField(required=True)


class OrganizationCreateSerializer(serializers.Serializer):
    organization_name = serializers.CharField(required=True)
    organization_type = serializers.CharField(required=True)
    organization_phone = serializers.CharField(required=True)
    organization_email = serializers.EmailField(required=True)
    organization_address = serializers.CharField(required=True)
    documentation = serializers.ListField(
        child=OrganizationCreateFilesSerializer(), required=False, allow_empty=True
    )

    def to_representation(self, instance):
        """Return organization data with files"""
        if isinstance(instance, Organization):
            serializer = OrganizationSerializer(instance)
            data = serializer.data
            # Add files data
            data["files"] = OrganizationFilesSerializer(
                instance.files.all(), many=True
            ).data
            return data
        return OrganizationSerializer(instance).data


class HealthProgramTypeSerializer(serializers.ModelSerializer):
    """
    Serializer for health program types
    """

    organizations_count = serializers.SerializerMethodField()

    class Meta:
        model = HealthProgramType
        fields = (
            "id",
            "name",
            "description",
            "default",
            "organizations_count",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def get_organizations_count(self, obj):
        return obj.organizations.count()


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

    class Meta:
        model = HealthProgram
        fields = [
            "id",
            "program_name",
            "program_type",
            "program_type_display",
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
            "partner_organizations",
            "funding_source",
            "status",
            "status_display",
            "is_active",
            "interventions_count",
            "is_synced",
            "locum_needs",
            "equipment_needs",
            "equipment_list",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "is_synced",
            "created_by",
        ]

    def get_created_by_name(self, obj):
        if obj.created_by:
            return f"{obj.created_by.first_name} {obj.created_by.last_name}"
        return None

    def get_interventions_count(self, obj):
        return obj.interventions.count()


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


class SurveyQuesitonOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = SurveyQuestionOption
        fields = (
            "id",
            "option",
        )


class SurveyQuestionSerializer(serializers.ModelSerializer):
    options = SurveyQuesitonOptionSerializer(many=True, read_only=True)

    class Meta:
        model = SurveyQuestion
        fields = (
            "id",
            "question",
            "question_type",
            "required",
            "options",
        )


class SurveySerializer(serializers.ModelSerializer):
    responses = serializers.SerializerMethodField(read_only=True)

    def get_responses(self, obj):
        return obj.responses.count()

    class Meta:
        model = Survey
        fields = (
            "id",
            "title",
            "description",
            "active",
            "end_date",
            "responses",
            "date_created",
            "last_updated",
        )
        read_only_fields = (
            "id",
            "date_created",
            "last_updated",
        )


class SurveyDetailSerializer(serializers.ModelSerializer):
    questions = SurveyQuestionSerializer(many=True, read_only=True)
    responses = serializers.SerializerMethodField(read_only=True)

    def get_responses(self, obj):
        return obj.responses.count()

    class Meta:
        model = Survey
        fields = (
            "id",
            "title",
            "description",
            "active",
            "end_date",
            "responses",
            "questions",
            "date_created",
            "last_updated",
        )
        read_only_fields = (
            "id",
            "date_created",
            "last_updated",
        )


class SurveyCreateOptionSerializer(serializers.Serializer):
    option = serializers.CharField(max_length=240)


class SurveyCreateQuestionSerializer(serializers.Serializer):
    question = serializers.CharField(max_length=240)
    question_type = serializers.ChoiceField(choices=SurveyQuestion.QuestionType.choices)
    required = serializers.BooleanField()
    options = serializers.ListField(child=SurveyCreateOptionSerializer())


class SurveyCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=240)
    description = serializers.CharField(max_length=240)
    end_date = serializers.DateField()
    questions = serializers.ListField(child=SurveyCreateQuestionSerializer())


class SurveyAnswersSerializer(serializers.Serializer):
    question = serializers.IntegerField()
    answer = serializers.CharField(max_length=240)


class SurveyAnswerCreateSerializer(serializers.Serializer):
    survey = serializers.IntegerField()
    phone_number = serializers.CharField(max_length=240, required=False)
    answers = serializers.ListField(child=SurveyAnswersSerializer())

    def validate(self, attr):
        if not attr.get("phone_number"):
            raise exceptions.GeneralException(detail="Phone Number is required")

        return attr


class SurveyQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = SurveyQuestion
        fields = (
            "question_type",
            "question",
            "required",
        )


class SurveyResponseAnswerSerializer(serializers.ModelSerializer):
    question = SurveyQuestionSerializer(read_only=True)

    class Meta:
        model = SurveyResponseAnswers
        fields = (
            "id",
            "question",
            "answer",
        )


class SurveyResponseSerializer(serializers.ModelSerializer):
    answers = SurveyResponseAnswerSerializer(many=True, read_only=True)

    class Meta:
        model = SurveyResponse
        fields = (
            "id",
            "survey",
            "phone_number",
            "answers",
            "date_created",
            "last_updated",
        )
        depth = 1


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


# Program Intervention Serializers
class ProgramInterventionTypeSerializer(serializers.ModelSerializer):
    """
    Serializer for program intervention types
    """

    organizations_count = serializers.SerializerMethodField()

    class Meta:
        model = ProgramInterventionType
        fields = (
            "id",
            "name",
            "description",
            "default",
            "organizations_count",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def get_organizations_count(self, obj):
        return obj.organizations.count()


class InterventionFieldOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = InterventionFieldOption
        fields = (
            "id",
            "option",
            "date_created",
            "last_updated",
        )
        read_only_fields = ("id", "date_created", "last_updated")


class InterventionFieldSerializer(serializers.ModelSerializer):
    options = InterventionFieldOptionSerializer(many=True, read_only=True)

    class Meta:
        model = InterventionField
        fields = (
            "id",
            "field_type",
            "name",
            "required",
            "options",
            "date_created",
            "last_updated",
        )
        read_only_fields = ("id", "date_created", "last_updated")


class ProgramInterventionSerializer(serializers.ModelSerializer):
    """
    Serializer for program interventions
    """

    intervention_type_name = serializers.CharField(
        source="intervention_type.name", read_only=True
    )
    program_name = serializers.CharField(source="program.program_name", read_only=True)
    fields_count = serializers.SerializerMethodField()
    responses_count = serializers.SerializerMethodField()

    class Meta:
        model = ProgramIntervention
        fields = (
            "id",
            "intervention_type",
            "intervention_type_name",
            "program",
            "program_name",
            "fields_count",
            "responses_count",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def get_fields_count(self, obj):
        return obj.fields.count()

    def get_responses_count(self, obj):
        return obj.intervention_responses.count()


class ProgramInterventionDetailSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for program interventions with fields
    """

    intervention_type_name = serializers.CharField(
        source="intervention_type.name", read_only=True
    )
    program_name = serializers.CharField(source="program.program_name", read_only=True)
    fields = InterventionFieldSerializer(many=True, read_only=True)
    responses_count = serializers.SerializerMethodField()

    class Meta:
        model = ProgramIntervention
        fields = (
            "id",
            "intervention_type",
            "intervention_type_name",
            "program",
            "program_name",
            "fields",
            "responses_count",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def get_responses_count(self, obj):
        return obj.intervention_responses.count()


class InterventionCreateOptionSerializer(serializers.Serializer):
    option = serializers.CharField(max_length=255)


class InterventionCreateFieldSerializer(serializers.Serializer):
    field_type = serializers.ChoiceField(choices=InterventionField.FieldType.choices)
    name = serializers.CharField(max_length=255)
    required = serializers.BooleanField()
    options = serializers.ListField(
        child=InterventionCreateOptionSerializer(), required=False, allow_empty=True
    )


class InterventionCreateSerializer(serializers.Serializer):
    intervention_type = serializers.UUIDField()
    program = serializers.UUIDField()
    fields = serializers.ListField(child=InterventionCreateFieldSerializer())

    def validate_intervention_type(self, value):
        try:
            return ProgramInterventionType.objects.get(id=value)
        except ProgramInterventionType.DoesNotExist:
            raise serializers.ValidationError("Invalid intervention type")

    def validate_program(self, value):
        try:
            return HealthProgram.objects.get(id=value)
        except HealthProgram.DoesNotExist:
            raise serializers.ValidationError("Invalid program")


class InterventionFieldResponseSerializer(serializers.ModelSerializer):
    """
    Serializer for intervention field responses
    """

    field_name = serializers.CharField(source="field.name", read_only=True)
    field_type = serializers.CharField(source="field.field_type", read_only=True)

    class Meta:
        model = InterventionResponseValue
        fields = (
            "id",
            "field",
            "field_name",
            "field_type",
            "value",
            "date_created",
            "last_updated",
        )
        read_only_fields = ("id", "date_created", "last_updated")


class InterventionResponseSerializer(serializers.ModelSerializer):
    """
    Serializer for intervention responses
    """

    intervention_name = serializers.CharField(
        source="intervention.intervention_type.name", read_only=True
    )
    program_name = serializers.CharField(
        source="intervention.program.program_name", read_only=True
    )
    patient_name = serializers.SerializerMethodField()
    response_values = InterventionFieldResponseSerializer(many=True, read_only=True)

    class Meta:
        model = InterventionResponse
        fields = (
            "id",
            "intervention",
            "intervention_name",
            "program_name",
            "participant_id",
            "patient_record",
            "patient_name",
            "response_values",
            "date_created",
            "last_updated",
        )
        read_only_fields = ("id", "date_created", "last_updated")

    def get_patient_name(self, obj):
        if obj.patient_record:
            return f"{obj.patient_record.first_name} {obj.patient_record.surname}"
        return None


class InterventionFieldAnswerSerializer(serializers.Serializer):
    field = serializers.UUIDField()
    value = serializers.CharField()


class InterventionResponseCreateSerializer(serializers.Serializer):
    intervention = serializers.UUIDField()
    participant_id = serializers.CharField(
        max_length=15, required=False, allow_blank=True
    )
    patient_record = serializers.UUIDField(required=False, allow_null=True)
    answers = serializers.ListField(child=InterventionFieldAnswerSerializer())

    def validate_intervention(self, value):
        try:
            return ProgramIntervention.objects.get(id=value)
        except ProgramIntervention.DoesNotExist:
            raise serializers.ValidationError("Invalid intervention")

    def validate_patient_record(self, value):
        if value:
            try:
                from patients.models import PatientProfile

                return PatientProfile.objects.get(id=value)
            except PatientProfile.DoesNotExist:
                raise serializers.ValidationError("Invalid patient record")
        return None

    def validate(self, attr):
        if not attr.get("participant_id") and not attr.get("patient_record"):
            raise serializers.ValidationError(
                "Either participant_id or patient_record is required"
            )
        return attr
