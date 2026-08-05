from rest_framework import serializers
from .models import (
    HealthProgramInvitation,
    HealthProgramLocumNeed,
    Organization,
    HealthProgramType,
    HealthProgram,
    Participant,
    ProgramInterventionType,
    ProgramIntervention,
    InterventionField,
    InterventionFieldOption,
    InterventionResponse,
    InterventionResponseValue,
    BulkInterventionUpload,
    Survey,
    SurveyQuestionOption,
    SurveyQuestion,
    SurveyResponse,
    SurveyResponseAnswers,
    BulkSurveyUpload,
    OrganizationFiles,
    LocumJobRole,
    LocumJob,
    LocumJobApplication,
    HealthProgramPartners,
    Staff,
    CertificateTemplate,
    IssuedCertificate,
    InterventionTemplate,
    InterventionTemplateField,
)
from accounts.serializers import UserSerializer
from helpers import exceptions


class StaffSerializer(serializers.ModelSerializer):
    """
    Staff membership serializer
    """

    user_account = serializers.PrimaryKeyRelatedField(read_only=True)
    user_account_name = serializers.SerializerMethodField()
    display_role = serializers.CharField(read_only=True)
    effective_permissions = serializers.SerializerMethodField()

    def get_effective_permissions(self, obj):
        return obj.effective_permissions()

    def get_user_account_name(self, obj):
        u = obj.user_account
        if not u:
            return None
        return (u.get_full_name() or "").strip() or u.email

    class Meta:
        model = Staff
        fields = [
            "id",
            "account_type",
            "status",
            "organization",
            "user_account",
            "user_account_name",
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "role",
            "display_role",
            "is_clinical",
            "permissions",
            "effective_permissions",
            "bio",
            "invited_at",
            "accepted_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "organization",
            "user_account",
            "invited_at",
            "accepted_at",
            "created_at",
            "updated_at",
        ]


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
            "banner",
            "verified",
            "files",
            "slug",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class ShortOrganizationSerializer(serializers.ModelSerializer):
    """
    Organization serializer
    """

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
            "banner",
            "verified",
            "files",
            "slug",
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


class HealthProgramLocumNeedSerializer(serializers.ModelSerializer):
    """
    Serializer for health program locum needs
    """

    class Meta:
        model = HealthProgramLocumNeed
        fields = ["id", "program", "locum_job", "date_created", "last_updated"]
        read_only_fields = ["id", "date_created", "last_updated"]

    def get_locum_job_name(self, obj):
        return obj.locum_job.title


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
    approved_by_name = serializers.SerializerMethodField()
    is_active = serializers.BooleanField(read_only=True)
    participation_rate = serializers.FloatField(read_only=True)
    locum_needs = serializers.SerializerMethodField()
    is_owner = serializers.SerializerMethodField()

    class Meta:
        model = HealthProgram
        fields = [
            "id",
            "title_image",
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
            "equipment_needs",
            "locum_needs",
            "is_owner",
            "approval_reason",
            "approved_by",
            "approved_by_name",
            "approved_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "is_synced",
            "created_by",
            "actual_participants",
            "interventions_planned",
            "status",
        ]

    def get_created_by_name(self, obj):
        if obj.created_by:
            return f"{obj.created_by.first_name} {obj.created_by.last_name}"
        return None

    def get_approved_by_name(self, obj):
        if obj.approved_by:
            return f"{obj.approved_by.first_name} {obj.approved_by.last_name}"
        return None

    def get_is_owner(self, obj):
        """True only for the organization owner (not invited staff)."""
        request = self.context.get("request")
        if not request or not request.user or not request.user.is_authenticated:
            return False
        return bool(obj.organization and obj.organization.user_id == request.user.id)

    def get_locum_needs(self, obj):
        """Get locum needs for this program"""
        locum_needs = obj.locum_needs.all()
        return [
            {
                "id": need.id,
                "locum_job_id": need.locum_job.id,
                "locum_job_title": need.locum_job.title,
                "locum_job_role": (
                    need.locum_job.role.name if need.locum_job.role else None
                ),
                "locum_job_organization": (
                    need.locum_job.organization.organization_name
                    if need.locum_job.organization
                    else None
                ),
                "date_created": need.date_created,
            }
            for need in locum_needs
        ]


class ShortHealthProgramSerializer(serializers.ModelSerializer):
    """
    Serializer for health programs
    """

    program_type_display = serializers.CharField(
        source="get_program_type_display", read_only=True
    )
    organization_name = serializers.CharField(
        source="organization.organization_name", read_only=True
    )

    class Meta:
        model = HealthProgram
        fields = [
            "id",
            "title_image",
            "program_name",
            "program_type_display",
            "description",
            "organization_name",
            "start_date",
            "end_date",
        ]


class RecentHealthProgramSerializer(serializers.ModelSerializer):
    """
    Serializer for health programs
    """

    program_type_name = serializers.CharField(
        source="program_type.name", read_only=True
    )

    class Meta:
        model = HealthProgram
        fields = [
            "id",
            "title_image",
            "program_name",
            "program_type",
            "program_type_name",
            "description",
            "target_participants",
            "start_date",
            "end_date",
            "location_name",
            "district",
            "region",
            "latitude",
            "longitude",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
        ]


class HealthProgramCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating health programs with locum job needs
    """

    locum_job_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        allow_empty=True,
        write_only=True,
        help_text="List of LocumJob IDs to associate with this program",
    )

    class Meta:
        model = HealthProgram
        fields = [
            "title_image",
            "program_name",
            "program_type",
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
            "partner_organizations",
            "funding_source",
            "equipment_needs",
            "locum_job_ids",
        ]

    def validate_locum_job_ids(self, value):
        """Validate that all locum job IDs exist and are valid"""
        if not value:
            return value

        # Check if all locum jobs exist
        existing_jobs = LocumJob.objects.filter(id__in=value)
        if len(existing_jobs) != len(value):
            found_ids = set(str(job.id) for job in existing_jobs)
            requested_ids = set(str(job_id) for job_id in value)
            missing_ids = requested_ids - found_ids
            raise serializers.ValidationError(
                f"Invalid locum job IDs: {', '.join(missing_ids)}"
            )

        return value


# class ProgramInterventionSerializer(serializers.ModelSerializer):
#     """
#     Serializer for program interventions
#     """

#     intervention_type_display = serializers.CharField(
#         source="get_intervention_type_display", read_only=True
#     )
#     participant_gender_display = serializers.CharField(
#         source="get_participant_gender_display", read_only=True
#     )
#     documented_by_name = serializers.SerializerMethodField()
#     program_name = serializers.CharField(source="program.program_name", read_only=True)
#     referral_facility_name = serializers.CharField(
#         source="referral_facility.name", read_only=True
#     )

#     class Meta:
#         model = ProgramIntervention
#         fields = [
#             "id",
#             "program",
#             "program_name",
#             "intervention_type",
#             "intervention_type_display",
#             "intervention_name",
#             "description",
#             "participant_id",
#             "participant_name",
#             "participant_age",
#             "participant_gender",
#             "participant_gender_display",
#             "participant_phone",
#             "blood_pressure",
#             "temperature",
#             "pulse",
#             "weight",
#             "height",
#             "test_results",
#             "vaccine_administered",
#             "vaccine_dose_number",
#             "vaccine_batch_number",
#             "vaccination_date",
#             "symptoms",
#             "diagnosis",
#             "treatment_given",
#             "referral_needed",
#             "referral_facility",
#             "referral_facility_name",
#             "referral_notes",
#             "notes",
#             "follow_up_required",
#             "follow_up_date",
#             "documented_by",
#             "documented_by_name",
#             "synced_to_ehr",
#             "ehr_record_id",
#             "documented_at",
#             "updated_at",
#         ]
#         read_only_fields = ["id", "documented_at", "updated_at"]

#     def get_documented_by_name(self, obj):
#         if obj.documented_by:
#             return f"{obj.documented_by.first_name} {obj.documented_by.last_name}"
#         return None


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
    question = serializers.UUIDField()
    answer = serializers.CharField(max_length=240)


class SurveyAnswerCreateSerializer(serializers.Serializer):
    survey = serializers.UUIDField()
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

    field_name = serializers.CharField(source="question.question", read_only=True)
    field_type = serializers.CharField(source="question.question_type", read_only=True)

    class Meta:
        model = SurveyResponseAnswers
        fields = (
            "id",
            "response",
            "field_name",
            "field_type",
            "answer",
        )


class SurveyResponseSerializer(serializers.ModelSerializer):
    answers = SurveyResponseAnswerSerializer(many=True, read_only=True)
    survey_title = serializers.CharField(source="survey.title", read_only=True)

    class Meta:
        model = SurveyResponse
        fields = (
            "id",
            "survey",
            "survey_title",
            "phone_number",
            "answers",
            "date_created",
            "last_updated",
        )
        # depth = 1


class SurveyFormFieldOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = SurveyQuestionOption
        fields = ("id", "option")


class SurveyFormFieldsSerializer(serializers.ModelSerializer):
    options = SurveyFormFieldOptionSerializer(many=True, read_only=True)

    class Meta:
        model = SurveyQuestion
        fields = (
            "id",
            "question_type",
            "question",
            "required",
            "options",
        )
        read_only_fields = ("id",)


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
    section_label = serializers.CharField(source="get_section_display", read_only=True)

    class Meta:
        model = InterventionField
        fields = (
            "id",
            "field_type",
            "section",
            "section_label",
            "field_key",
            "is_computed",
            "name",
            "required",
            "order",
            "options",
            "date_created",
            "last_updated",
        )
        # is_computed is derived from field_key on save, never client-set.
        read_only_fields = ("id", "is_computed", "date_created", "last_updated")


class ProgramInterventionSerializer(serializers.ModelSerializer):
    """
    Serializer for program interventions
    """

    intervention_type_name = serializers.CharField(
        source="intervention_type.name", read_only=True
    )
    # The organiser's own name, falling back to the type when unset so lists
    # never render a blank heading.
    display_title = serializers.CharField(read_only=True)
    program_name = serializers.CharField(source="program.program_name", read_only=True)
    fields_count = serializers.SerializerMethodField()
    responses_count = serializers.SerializerMethodField()

    class Meta:
        model = ProgramIntervention
        fields = (
            "id",
            "intervention_type",
            "intervention_type_name",
            "title",
            "display_title",
            "program",
            "program_name",
            "fields_count",
            "responses_count",
            "created_by",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_by", "created_at", "updated_at")

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
    # The organiser's own name, falling back to the type when unset so lists
    # never render a blank heading.
    display_title = serializers.CharField(read_only=True)
    program_name = serializers.CharField(source="program.program_name", read_only=True)
    fields = InterventionFieldSerializer(many=True, read_only=True)
    responses_count = serializers.SerializerMethodField()

    class Meta:
        model = ProgramIntervention
        fields = (
            "id",
            "intervention_type",
            "intervention_type_name",
            "title",
            "display_title",
            "program",
            "program_name",
            "fields",
            "responses_count",
            "created_by",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_by", "created_at", "updated_at")

    def get_responses_count(self, obj):
        return obj.intervention_responses.count()


class InterventionCreateOptionSerializer(serializers.Serializer):
    option = serializers.CharField(max_length=255)


class InterventionCreateFieldSerializer(serializers.Serializer):
    field_type = serializers.ChoiceField(choices=InterventionField.FieldType.choices)
    name = serializers.CharField(max_length=255)
    required = serializers.BooleanField()
    # The three-part data-entry structure agreed in the 13 July 2026 review.
    section = serializers.ChoiceField(
        choices=InterventionField.Section.choices,
        required=False,
        default=InterventionField.Section.INTERVENTION,
    )
    # Tags a standard measurement so the platform can derive BMI, carry vitals
    # across interventions and chart them.
    field_key = serializers.ChoiceField(
        choices=InterventionField.FieldKey.choices,
        required=False,
        allow_null=True,
        allow_blank=True,
    )
    options = serializers.ListField(
        child=InterventionCreateOptionSerializer(), required=False, allow_empty=True
    )

    def validate(self, attrs):
        # Empty string comes back from a "no tag" dropdown; store NULL so the
        # unique/lookup semantics stay clean.
        if attrs.get("field_key") == "":
            attrs["field_key"] = None
        return attrs


class InterventionCreateSerializer(serializers.Serializer):
    intervention_type = serializers.UUIDField()
    # The organiser's own name for this intervention. Optional — it falls back
    # to the type name — but one programme often runs several interventions of
    # the same type, and without it they are indistinguishable in every list.
    title = serializers.CharField(max_length=255, required=False, allow_blank=True)
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


class InterventionUpdateOptionSerializer(serializers.Serializer):
    id = serializers.UUIDField(required=False, allow_null=True)
    option = serializers.CharField(max_length=255)


class InterventionUpdateFieldSerializer(serializers.Serializer):
    id = serializers.UUIDField(required=False, allow_null=True)
    field_type = serializers.ChoiceField(choices=InterventionField.FieldType.choices)
    name = serializers.CharField(max_length=255)
    required = serializers.BooleanField()
    # The three-part data-entry structure agreed in the 13 July 2026 review.
    section = serializers.ChoiceField(
        choices=InterventionField.Section.choices,
        required=False,
        default=InterventionField.Section.INTERVENTION,
    )
    # Tags a standard measurement so the platform can derive BMI, carry vitals
    # across interventions and chart them.
    field_key = serializers.ChoiceField(
        choices=InterventionField.FieldKey.choices,
        required=False,
        allow_null=True,
        allow_blank=True,
    )
    options = serializers.ListField(
        child=InterventionUpdateOptionSerializer(), required=False, allow_empty=True
    )

    def validate(self, attrs):
        if attrs.get("field_key") == "":
            attrs["field_key"] = None
        return attrs


class InterventionUpdateSerializer(serializers.Serializer):
    intervention_type = serializers.UUIDField(required=False, allow_null=True)
    # Renaming is allowed after the fact; a title chosen while setting up an
    # event is often refined once the event is under way.
    title = serializers.CharField(max_length=255, required=False, allow_blank=True)
    program = serializers.UUIDField(required=False, allow_null=True)
    fields = serializers.ListField(
        child=InterventionUpdateFieldSerializer(), required=False, allow_empty=True
    )

    def validate_intervention_type(self, value):
        if value is None:
            return None
        try:
            return ProgramInterventionType.objects.get(id=value)
        except ProgramInterventionType.DoesNotExist:
            raise serializers.ValidationError("Invalid intervention type")

    def validate_program(self, value):
        if value is None:
            return None
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


class ParticipantReadSerializer(serializers.ModelSerializer):
    """
    How a participant is rendered on a saved record.

    Was also called `ParticipantSerializer`, which the input serializer further
    down silently shadowed — anything defined after that point got the wrong
    one. Renamed so the two cannot be confused again.
    """

    class Meta:
        model = Participant
        fields = (
            # The handle a client needs to pull this person's records in other
            # interventions. Its absence is what kept those records unlinked.
            "id",
            "participant_code",
            "fullname",
            "phone_number",
            "gender",
            "email",
            "age",
            "location",
        )
        read_only_fields = fields


class InterventionResponseSerializer(serializers.ModelSerializer):
    """
    Serializer for intervention responses
    """

    # Prefers the organiser's own title, falling back to the type name. Two
    # interventions of the same type in one programme were otherwise identical
    # everywhere a response is listed.
    intervention_name = serializers.CharField(
        source="intervention.display_title", read_only=True
    )
    program_name = serializers.CharField(
        source="intervention.program.program_name", read_only=True
    )
    response_values = InterventionFieldResponseSerializer(many=True, read_only=True)
    participant = ParticipantReadSerializer(read_only=True)
    created_by_name = serializers.SerializerMethodField()
    updated_by_name = serializers.SerializerMethodField()

    class Meta:
        model = InterventionResponse
        fields = (
            "id",
            "intervention",
            "intervention_name",
            "program_name",
            "participant",
            "response_values",
            "created_by_name",
            "updated_by_name",
            "date_created",
            "last_updated",
        )
        read_only_fields = ("id", "date_created", "last_updated")

    def _user_label(self, user):
        if not user:
            return None
        return (user.get_full_name() or "").strip() or user.email

    def get_created_by_name(self, obj):
        return self._user_label(obj.created_by)

    def get_updated_by_name(self, obj):
        return self._user_label(obj.updated_by)

    def get_patient_name(self, obj):
        if obj.patient_record:
            return f"{obj.patient_record.first_name} {obj.patient_record.surname}"
        return None


class InterventionFieldAnswerSerializer(serializers.Serializer):
    field = serializers.UUIDField()
    value = serializers.CharField()


class ParticipantSerializer(serializers.Serializer):
    """
    Standard participant information captured at registration, identical across
    every intervention (13 July 2026 review, items e and g).

    Input only. `ParticipantReadSerializer` renders saved records.
    """

    fullname = serializers.CharField(max_length=255, required=False, allow_blank=True)
    # Optional: outreach participants frequently have no phone, or decline to
    # give one. The auto-assigned participant_code is the identifier now, so a
    # missing number no longer blocks registration.
    phone_number = serializers.CharField(
        max_length=15, required=False, allow_blank=True
    )
    # Lets a returning participant be matched on the code from their slip
    # instead of their phone number.
    participant_code = serializers.CharField(
        max_length=20, required=False, allow_blank=True
    )
    gender = serializers.ChoiceField(
        choices=Participant.Gender.choices, required=False, allow_blank=True
    )
    email = serializers.EmailField(required=False, allow_blank=True)
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    age = serializers.IntegerField(
        required=False, allow_null=True, min_value=0, max_value=130
    )
    location = serializers.CharField(
        max_length=255, required=False, allow_blank=True
    )


class InterventionResponseCreateSerializer(serializers.Serializer):
    intervention = serializers.UUIDField()
    participant = ParticipantSerializer()
    answers = serializers.ListField(child=InterventionFieldAnswerSerializer())
    # Set when transcribing paper slips after an event so reports reflect when
    # the data was collected, not when it was typed up (item k).
    recorded_at = serializers.DateTimeField(required=False, allow_null=True)
    entry_mode = serializers.ChoiceField(
        choices=["live", "transcribed", "imported"], required=False
    )
    # Lets a pre-printed queue slip be filled in rather than creating a new row.
    participant_id = serializers.UUIDField(required=False, allow_null=True)

    def validate_intervention(self, value):
        try:
            return ProgramIntervention.objects.get(id=value)
        except ProgramIntervention.DoesNotExist:
            raise serializers.ValidationError("Invalid intervention")


class InterventionResponseUpdateSerializer(serializers.Serializer):
    participant_id = serializers.CharField(
        max_length=15, required=False, allow_blank=True
    )
    patient_record = serializers.UUIDField(required=False, allow_null=True)
    answers = serializers.ListField(
        child=InterventionFieldAnswerSerializer(), required=False
    )

    def validate_patient_record(self, value):
        if value:
            try:
                from patients.models import PatientProfile

                return PatientProfile.objects.get(id=value)
            except PatientProfile.DoesNotExist:
                raise serializers.ValidationError("Invalid patient record")
        return None

    def validate(self, attrs):
        response = self.context.get("response")
        if response is None:
            raise serializers.ValidationError("Response context is required")

        participant_provided = "participant_id" in attrs
        patient_provided = "patient_record" in attrs
        answers_provided = "answers" in attrs

        if not any([participant_provided, patient_provided, answers_provided]):
            raise serializers.ValidationError("No fields provided for update")

        final_participant = attrs.get("participant_id", response.participant_id)
        if isinstance(final_participant, str) and not final_participant.strip():
            final_participant = None

        final_patient = attrs.get("patient_record", response.patient_record)

        if not final_participant and not final_patient:
            raise serializers.ValidationError(
                "Either participant_id or patient_record must be provided"
            )

        return attrs


class InterventionFieldOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = InterventionFieldOption
        fields = ("id", "id", "option")


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
        )
        read_only_fields = ("id", "date_created", "last_updated")


# Locum Job Serializers
class LocumJobRoleSerializer(serializers.ModelSerializer):
    """
    Serializer for locum job roles
    """

    organizations_count = serializers.SerializerMethodField()

    class Meta:
        model = LocumJobRole
        fields = (
            "id",
            "name",
            "description",
            "organizations_count",
            "default",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def get_organizations_count(self, obj):
        return obj.organization.count()


class LocumJobSerializer(serializers.ModelSerializer):
    """
    Serializer for locum jobs
    """

    role_name = serializers.CharField(source="role.name", read_only=True)
    accepts_non_professionals = serializers.BooleanField(read_only=True)
    organization_name = serializers.CharField(
        source="organization.organization_name", read_only=True
    )
    organization_type = serializers.CharField(
        source="organization.organization_type", read_only=True
    )
    renumeration_display = serializers.SerializerMethodField()
    is_expired = serializers.BooleanField(read_only=True)
    is_accepting_applications = serializers.BooleanField(read_only=True)

    class Meta:
        model = LocumJob
        fields = (
            "id",
            "role",
            "role_name",
            "title",
            "organization",
            "organization_name",
            "organization_type",
            "description",
            "requirements",
            "location",
            "title_image",
            "job_type",
            "open_to_non_professionals",
            "accepts_non_professionals",
            "renumeration",
            "renumeration_frequency",
            "renumeration_display",
            "currency",
            "is_active",
            "approved",
            "is_expired",
            "is_accepting_applications",
            "slug",
            "date_created",
            "last_updated",
        )
        read_only_fields = ("id", "date_created", "last_updated")

    def validate(self, attrs):
        # Same rule as on create: a paid role is never open to
        # non-professionals, so an edit cannot store a flag the platform
        # would then ignore.
        job_type = attrs.get(
            "job_type", getattr(self.instance, "job_type", "paid")
        )
        if job_type != "volunteering":
            attrs["open_to_non_professionals"] = False
        return attrs

    def get_renumeration_display(self, obj):
        """Format renumeration with frequency"""
        if obj.job_type == "volunteering":
            return "Volunteering"
        if obj.renumeration and obj.renumeration_frequency:
            return f"{obj.renumeration} per {obj.renumeration_frequency}"
        return None


class LocumJobCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating locum jobs
    """

    class Meta:
        model = LocumJob
        fields = (
            "role",
            "title",
            "organization",
            "description",
            "requirements",
            "location",
            "title_image",
            "job_type",
            "renumeration",
            "renumeration_frequency",
            "currency",
            # Volunteer eligibility (13 July 2026 review, item n). Absent from
            # this list the flag was silently dropped on create, so a role
            # could only ever be opened up by a later edit.
            "open_to_non_professionals",
            "is_active",
            "approved",
        )

    def validate(self, attrs):
        """Validate that renumeration fields are provided for paid jobs"""
        job_type = attrs.get("job_type", "paid")
        renumeration = attrs.get("renumeration")
        renumeration_frequency = attrs.get("renumeration_frequency")

        if job_type == "paid":
            if not renumeration:
                raise serializers.ValidationError(
                    {"renumeration": "Renumeration is required for paid jobs."}
                )
            if not renumeration_frequency:
                raise serializers.ValidationError(
                    {
                        "renumeration_frequency": "Renumeration frequency is required for paid jobs."
                    }
                )
        elif job_type == "volunteering":
            # Clear renumeration fields for volunteering jobs if provided
            if renumeration is not None or renumeration_frequency:
                # Allow it but warn or clear - for now we'll just ignore it
                pass

        # A paid role is never open to non-professionals. `accepts_non_
        # professionals` already enforces this when reading, but storing a
        # `True` that the platform ignores makes the admin and the API
        # disagree with the behaviour — so normalise it on the way in.
        if job_type != "volunteering":
            attrs["open_to_non_professionals"] = False

        return attrs


class LocumJobDetailSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for locum jobs with related data
    """

    role_name = serializers.CharField(source="role.name", read_only=True)
    accepts_non_professionals = serializers.BooleanField(read_only=True)
    role_description = serializers.CharField(source="role.description", read_only=True)
    organization_name = serializers.CharField(
        source="organization.organization_name", read_only=True
    )
    organization_type = serializers.CharField(
        source="organization.organization_type", read_only=True
    )
    organization_description = serializers.CharField(
        source="organization.description", read_only=True
    )
    renumeration_display = serializers.SerializerMethodField()
    is_expired = serializers.BooleanField(read_only=True)
    is_accepting_applications = serializers.BooleanField(read_only=True)

    class Meta:
        model = LocumJob
        fields = (
            "id",
            "role",
            "role_name",
            "role_description",
            "title",
            "organization",
            "organization_name",
            "organization_type",
            "organization_description",
            "description",
            "requirements",
            "location",
            "title_image",
            "job_type",
            "open_to_non_professionals",
            "accepts_non_professionals",
            "renumeration",
            "renumeration_frequency",
            "renumeration_display",
            "currency",
            "is_active",
            "approved",
            "is_expired",
            "is_accepting_applications",
            "slug",
            "date_created",
            "last_updated",
        )
        read_only_fields = ("id", "date_created", "last_updated")

    def get_renumeration_display(self, obj):
        """Format renumeration with frequency"""
        if obj.job_type == "volunteering":
            return "Volunteering"
        if obj.renumeration and obj.renumeration_frequency:
            return f"{obj.renumeration} per {obj.renumeration_frequency}"
        return None


class LocumJobApplicationSerializer(serializers.ModelSerializer):
    """
    Serializer for locum job applications
    """

    job_title = serializers.CharField(source="job.title", read_only=True)
    applicant_email = serializers.EmailField(source="applicant.email", read_only=True)
    applicant_type_display = serializers.CharField(
        source="get_applicant_type_display", read_only=True
    )
    applicant_name = serializers.SerializerMethodField()
    organization = serializers.SerializerMethodField()

    def get_organization(self, obj):
        return obj.job.organization.id

    class Meta:
        model = LocumJobApplication
        fields = (
            "id",
            "job",
            "job_title",
            "applicant",
            "organization",
            "applicant_name",
            "applicant_email",
            "full_name",
            "email",
            "phone_number",
            "resume",
            "cover_letter",
            "years_of_experience",
            "applicant_type",
            "applicant_type_display",
            "background",
            "status",
            "applied_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "applicant",
            "applicant_name",
            "applicant_email",
            # Derived from the account server-side; an applicant must not be
            # able to declare themselves a health professional.
            "applicant_type",
            "applicant_type_display",
            "applied_at",
            "updated_at",
            "status",
        )
        extra_kwargs = {
            "full_name": {"required": False},
            "email": {"required": False},
            "phone_number": {"required": False},
            "resume": {"required": False},
            "cover_letter": {"required": False},
            "years_of_experience": {"required": False},
        }

    def get_applicant_name(self, obj):
        if obj.applicant:
            return (
                f"{obj.applicant.first_name} {obj.applicant.last_name}".strip()
                or obj.applicant.email
            )
        return None


# Health Program Partners Serializers
class HealthProgramPartnersSerializer(serializers.ModelSerializer):
    """
    Serializer for health program partners
    """

    class Meta:
        model = HealthProgramPartners
        fields = (
            "id",
            "name",
            "logo",
            "url",
            "date_created",
            "last_updated",
        )
        read_only_fields = ("id", "date_created", "last_updated")


class HealthProgramPartnersCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating health program partners
    """

    class Meta:
        model = HealthProgramPartners
        fields = (
            "name",
            "logo",
            "url",
        )


class HealthProgramInvitationSerializer(serializers.ModelSerializer):
    program = ShortHealthProgramSerializer(read_only=True)
    invited_to = UserSerializer(read_only=True)
    locum_job_title = serializers.SerializerMethodField()

    class Meta:
        model = HealthProgramInvitation
        fields = (
            "id",
            "program",
            "intervention",
            "status",
            "source",
            "locum_job_title",
            "message",
            "link",
            "expires_at",
            "invited_by",
            "invited_to",
        )

        read_only_fields = (
            "id",
            "status",
            "source",
            "locum_job_title",
            "link",
            "expires_at",
            "invited_by",
        )

    def get_locum_job_title(self, obj):
        if obj.locum_application_id and obj.locum_application.job_id:
            return obj.locum_application.job.title
        return None


class HealthProgramInvitationDetailSerializer(serializers.ModelSerializer):
    program = HealthProgramSerializer(read_only=True)
    intervention = ProgramInterventionSerializer(many=True, read_only=True)
    invited_by = ShortOrganizationSerializer(read_only=True)
    invited_to = UserSerializer(read_only=True)

    class Meta:
        model = HealthProgramInvitation
        fields = (
            "id",
            "program",
            "intervention",
            "invited_by",
            "invited_to",
            "status",
        )


class HealthProgramInvitationCreateSerializer(serializers.Serializer):
    intervention = serializers.ListField(child=serializers.UUIDField())
    message = serializers.CharField(required=False, allow_null=True)
    invited_to = serializers.ListField(child=serializers.UUIDField())


# =============================================================================
# CERTIFICATE SERIALIZERS
# =============================================================================

class CertificateTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CertificateTemplate
        fields = [
            "id",
            "name",
            "description",
            "template_type",
            "builtin_style",
            "background_image",
            "pdf_template",
            "primary_color",
            "secondary_color",
            "accent_color",
            "custom_logo",
            "header_text",
            "body_text",
            "footer_text",
            "signatory_name",
            "signatory_title",
            "signatory_signature",
            "show_qr_code",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class IssuedCertificateSerializer(serializers.ModelSerializer):
    program_name = serializers.CharField(source="program.program_name", read_only=True)
    template_name = serializers.CharField(source="template.name", read_only=True)
    certificate_file_url = serializers.SerializerMethodField()

    class Meta:
        model = IssuedCertificate
        fields = [
            "id",
            "program",
            "program_name",
            "invitation",
            "template",
            "template_name",
            "recipient_name",
            "recipient_email",
            "issued_at",
            "certificate_file",
            "certificate_file_url",
            "verification_code",
            "is_emailed",
            "emailed_at",
            "metadata",
        ]
        read_only_fields = [
            "id",
            "issued_at",
            "certificate_file",
            "certificate_file_url",
            "verification_code",
            "is_emailed",
            "emailed_at",
        ]

    def get_certificate_file_url(self, obj):
        request = self.context.get("request")
        if obj.certificate_file and request:
            return request.build_absolute_uri(obj.certificate_file.url)
        return None


class IssueCertificatesSerializer(serializers.Serializer):
    """Payload for bulk-issuing certificates for a program."""
    # Deprecated/optional: BridgeCare now uses one fixed certificate design.
    template_id = serializers.UUIDField(required=False, allow_null=True)
    invitation_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        default=list,
        help_text="Leave empty to issue to ALL accepted invitees.",
    )
    send_email = serializers.BooleanField(default=True)


class InterventionTemplateFieldSerializer(serializers.ModelSerializer):
    section_label = serializers.CharField(source="get_section_display", read_only=True)

    class Meta:
        model = InterventionTemplateField
        fields = (
            "id",
            "name",
            "field_type",
            "section",
            "section_label",
            "field_key",
            "is_computed",
            "required",
            "order",
            "options",
        )
        read_only_fields = ("id",)


class InterventionTemplateSerializer(serializers.ModelSerializer):
    """
    A reusable field set an organiser can apply when creating an intervention
    (13 July 2026 review, item h).
    """

    fields = InterventionTemplateFieldSerializer(many=True, required=False)
    intervention_type_name = serializers.CharField(
        source="intervention_type.name", read_only=True
    )
    field_count = serializers.SerializerMethodField()

    class Meta:
        model = InterventionTemplate
        fields = (
            "id",
            "name",
            "description",
            "intervention_type",
            "intervention_type_name",
            "organization",
            "is_platform_default",
            "is_active",
            "fields",
            "field_count",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "organization",
            "is_platform_default",
            "created_at",
            "updated_at",
        )

    def get_field_count(self, obj):
        return obj.fields.count()

    def create(self, validated_data):
        fields_data = validated_data.pop("fields", [])
        template = InterventionTemplate.objects.create(**validated_data)
        self._sync_fields(template, fields_data)
        return template

    def update(self, instance, validated_data):
        fields_data = validated_data.pop("fields", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if fields_data is not None:
            # Templates are edited as a whole list, so replace rather than
            # trying to diff positions the client may have reordered.
            instance.fields.all().delete()
            self._sync_fields(instance, fields_data)
        return instance

    @staticmethod
    def _sync_fields(template, fields_data):
        for index, field_data in enumerate(fields_data):
            field_data.setdefault("order", index)
            # Mirror the InterventionField rules so a template can never define
            # an editable BMI or a numeric blood-pressure field.
            if field_data.get("field_key") == InterventionField.FieldKey.BMI:
                field_data["is_computed"] = True
            if (
                field_data.get("field_key")
                == InterventionField.FieldKey.BLOOD_PRESSURE
            ):
                field_data["field_type"] = InterventionField.FieldType.TEXT
            InterventionTemplateField.objects.create(template=template, **field_data)
