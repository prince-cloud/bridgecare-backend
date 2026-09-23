"""Admin API resources for the communities app."""
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.response import Response

from communities.models import (
    Organization,
    Staff,
    OrganizationFiles,
    LocumJobRole,
    HealthProgram,
    HealthProgramType,
    Participant,
    ProgramIntervention,
    InterventionResponse,
    BulkInterventionUpload,
    Survey,
    SurveyResponse,
    LocumJob,
    LocumJobApplication,
    IssuedCertificate,
    CertificateTemplate,
    HealthProgramPartners,
    HealthProgramLocumNeed,
    ProgramInterventionType,
    ProgramIntervention,
    HealthProgramInvitation,
    InterventionField,
    InterventionFieldOption,
    InterventionResponse,
    InterventionResponseValue,
    InterventionTemplate,
    InterventionTemplateField,
    BulkInterventionUpload,
    SurveyType,
    Survey,
    SurveyQuestion,
    SurveyQuestionOption,
    SurveyResponse,
    SurveyResponseAnswers,
    BulkSurveyUpload,
)
from communities.serializers import (
    OrganizationSerializer,
    StaffSerializer,
    OrganizationFilesSerializer,
    HealthProgramSerializer,
    ShortHealthProgramSerializer,
    HealthProgramTypeSerializer,
    ProgramInterventionDetailSerializer,
    InterventionResponseSerializer,
    BulkInterventionUploadSerializer,
    SurveySerializer,
    SurveyDetailSerializer,
    SurveyResponseSerializer,
    LocumJobSerializer,
    LocumJobDetailSerializer,
    LocumJobApplicationSerializer,
    IssuedCertificateSerializer,
    CertificateTemplateSerializer,
    LocumJobRoleSerializer,
    ProgramInterventionTypeSerializer,
    InterventionFieldSerializer,
    InterventionFieldOptionSerializer,
    HealthProgramInvitationSerializer,
    BulkInterventionUploadSerializer,
    SurveyQuesitonOptionSerializer,
    SurveyQuestionSerializer,
    SurveyDetailSerializer,
)
from admin_api.base import AdminModelViewSet, AdminReadOnlyViewSet


class HealthProgramPartnersAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = HealthProgramPartners
        fields = "__all__"
        read_only_fields = ("id", "date_created", "last_updated")


class HealthProgramLocumNeedAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = HealthProgramLocumNeed
        fields = "__all__"
        read_only_fields = ("id", "date_created", "last_updated")


class LocumJobAdminSerializer(serializers.ModelSerializer):
    """Admin write view — covers every field for back-office management."""

    class Meta:
        model = LocumJob
        fields = "__all__"
        read_only_fields = ("id", "slug", "title_image", "date_created", "last_updated")


class OrganizationAdminViewSet(AdminModelViewSet):
    queryset = Organization.objects.select_related("user").all()
    serializer_class = OrganizationSerializer
    search_fields = ["organization_name", "organization_email", "registration_number"]
    filterset_fields = ["organization_type", "verified"]
    ordering_fields = ["created_at", "organization_name", "verified"]
    facet_fields = ["verified"]

    @action(detail=True, methods=["post"])
    def verify(self, request, pk=None):
        org = self.get_object(); org.verified = True; org.save()
        return Response(OrganizationSerializer(org).data)

    @action(detail=True, methods=["post"])
    def unverify(self, request, pk=None):
        org = self.get_object(); org.verified = False; org.save()
        return Response(OrganizationSerializer(org).data)


class OrganizationStaffAdminViewSet(AdminModelViewSet):
    queryset = Staff.objects.select_related("organization", "user_account").all()
    serializer_class = StaffSerializer
    search_fields = ["first_name", "last_name", "email"]
    filterset_fields = ["organization", "account_type", "status"]
    ordering_fields = ["created_at"]
    facet_fields = ["organization", "status", "account_type"]

    @action(detail=True, methods=["post"])
    def revoke(self, request, pk=None):
        m = self.get_object(); m.status = Staff.Status.REVOKED; m.save()
        return Response(StaffSerializer(m).data)

    @action(detail=True, methods=["post"])
    def reactivate(self, request, pk=None):
        m = self.get_object(); m.status = Staff.Status.ACTIVE; m.save()
        return Response(StaffSerializer(m).data)


class OrganizationFilesAdminViewSet(AdminReadOnlyViewSet):
    queryset = OrganizationFiles.objects.select_related("organization").all()
    serializer_class = OrganizationFilesSerializer
    search_fields = ["file_name", "organization__organization_name"]
    filterset_fields = ["document_type", "organization"]
    ordering_fields = ["created_at"]
    facet_fields = ["organization", "document_type"]


class HealthProgramAdminViewSet(AdminModelViewSet):
    queryset = HealthProgram.objects.select_related("organization", "program_type").all()
    serializer_class = HealthProgramSerializer
    search_fields = ["program_name"]
    filterset_fields = ["status", "program_type", "organization", "region"]
    ordering_fields = ["created_at", "start_date", "program_name", "status", "region", "organization"]
    facet_fields = ["status", "region"]

    def perform_create(self, serializer):
        # created_by is a required FK — attribute admin-created programs to the operator.
        super().perform_create(serializer, created_by=self.request.user)

    def _set_status(self, pk, value):
        program = self.get_object(); program.status = value; program.save()
        return Response(HealthProgramSerializer(program).data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        return self._set_status(pk, "approved")

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        return self._set_status(pk, "rejected")

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        return self._set_status(pk, "cancelled")


class InterventionAdminViewSet(AdminReadOnlyViewSet):
    queryset = ProgramIntervention.objects.select_related("intervention_type", "program").all()
    serializer_class = ProgramInterventionDetailSerializer
    filterset_fields = ["intervention_type", "program"]
    ordering_fields = ["created_at"]
    facet_fields = ["intervention_type", "program"]


class InterventionResponseAdminViewSet(AdminReadOnlyViewSet):
    queryset = InterventionResponse.objects.select_related("intervention", "participant").all()
    serializer_class = InterventionResponseSerializer
    filterset_fields = ["intervention", "participant", "entry_mode"]
    ordering_fields = ["date_created"]
    facet_fields = ["intervention", "entry_mode"]


class BulkInterventionUploadAdminViewSet(AdminReadOnlyViewSet):
    queryset = BulkInterventionUpload.objects.select_related("program").all()
    serializer_class = BulkInterventionUploadSerializer
    filterset_fields = ["status", "program"]
    ordering_fields = ["uploaded_at"]
    facet_fields = ["program", "status"]


class ParticipantAdminSerializer(serializers.ModelSerializer):
    """Admin write view of a program participant (the app serializer is a
    read-shaped Serializer, not a ModelSerializer)."""

    program_name = serializers.CharField(source="program.program_name", read_only=True, default=None)

    class Meta:
        model = Participant
        fields = "__all__"
        read_only_fields = ("participant_code", "participant_number", "last_updated")


class ParticipantAdminViewSet(AdminModelViewSet):
    queryset = Participant.objects.select_related("program", "organization").all()
    serializer_class = ParticipantAdminSerializer
    search_fields = ["fullname", "participant_code", "phone_number", "email"]
    filterset_fields = ["program", "gender", "organization"]
    ordering_fields = ["date_created", "participant_number"]
    facet_fields = ["program", "gender"]


class ProgramCatalogAdminViewSet(AdminModelViewSet):
    queryset = HealthProgramType.objects.all()
    serializer_class = HealthProgramTypeSerializer
    search_fields = ["name"]
    ordering_fields = ["name"]


class SurveyAdminViewSet(AdminModelViewSet):
    queryset = Survey.objects.select_related("survey_type", "created_by").all()
    serializer_class = SurveyDetailSerializer
    search_fields = ["title"]
    filterset_fields = ["active", "survey_type"]
    ordering_fields = ["date_created", "end_date"]
    facet_fields = ["survey_type", "active"]

    def get_serializer_class(self):
        if self.action == "list":
            return SurveySerializer
        return SurveyDetailSerializer

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        s = self.get_object(); s.active = True; s.save()
        return Response(SurveyDetailSerializer(s).data)

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        s = self.get_object(); s.active = False; s.save()
        return Response(SurveyDetailSerializer(s).data)


class SurveyResponseAdminViewSet(AdminReadOnlyViewSet):
    queryset = SurveyResponse.objects.select_related("survey").all()
    serializer_class = SurveyResponseSerializer
    search_fields = ["phone_number"]
    filterset_fields = ["survey"]
    ordering_fields = ["date_created"]
    facet_fields = ["survey"]


class LocumJobAdminViewSet(AdminModelViewSet):
    queryset = LocumJob.objects.select_related("organization", "role").all()
    serializer_class = LocumJobAdminSerializer
    search_fields = ["title", "location"]
    filterset_fields = ["job_type", "is_active", "approved", "organization", "role"]
    ordering_fields = ["date_created"]
    facet_fields = ["organization", "job_type", "approved", "is_active"]

    def get_serializer_class(self):
        if self.action == "list":
            return LocumJobSerializer
        return LocumJobDetailSerializer

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        j = self.get_object(); j.approved = True; j.save()
        return Response(LocumJobDetailSerializer(j).data)

    @action(detail=True, methods=["post"])
    def unapprove(self, request, pk=None):
        j = self.get_object(); j.approved = False; j.save()
        return Response(LocumJobDetailSerializer(j).data)

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        j = self.get_object(); j.is_active = False; j.save()
        return Response(LocumJobDetailSerializer(j).data)


class LocumApplicationAdminViewSet(AdminReadOnlyViewSet):
    queryset = LocumJobApplication.objects.select_related("job", "applicant").all()
    serializer_class = LocumJobApplicationSerializer
    search_fields = ["full_name", "email"]
    filterset_fields = ["status", "job", "applicant_type"]
    ordering_fields = ["applied_at"]
    facet_fields = ["job", "status", "applicant_type"]


class IssuedCertificateAdminViewSet(AdminReadOnlyViewSet):
    queryset = IssuedCertificate.objects.select_related("program").all()
    serializer_class = IssuedCertificateSerializer
    search_fields = ["recipient_name", "recipient_email", "verification_code"]
    filterset_fields = ["is_emailed", "program"]
    ordering_fields = ["issued_at"]

    @action(detail=True, methods=["post"], url_path="resend-email")
    def resend_email(self, request, pk=None):
        from accounts.tasks import send_certificate_email

        cert = self.get_object()
        send_certificate_email.delay(str(cert.id), send_email=True, force_resend=True)
        return Response({"detail": "Certificate email queued."})


class CertificateTemplateAdminViewSet(AdminReadOnlyViewSet):
    queryset = CertificateTemplate.objects.select_related("organization").all()
    serializer_class = CertificateTemplateSerializer
    filterset_fields = ["template_type", "is_active", "organization"]
    ordering_fields = ["created_at"]


class LocumJobRoleAdminViewSet(AdminReadOnlyViewSet):
    queryset = LocumJobRole.objects.all()
    serializer_class = LocumJobRoleSerializer
    search_fields = ["name"]
    filterset_fields = ["default"]
    ordering_fields = ["name"]
    facet_fields = ["default"]


class HealthProgramPartnersAdminViewSet(AdminReadOnlyViewSet):
    queryset = HealthProgramPartners.objects.all()
    serializer_class = HealthProgramPartnersAdminSerializer
    search_fields = ["name"]
    filterset_fields = []
    ordering_fields = ["date_created", "name"]


class ProgramLocumNeedAdminViewSet(AdminModelViewSet):
    queryset = HealthProgramLocumNeed.objects.select_related("program", "locum_job").all()
    serializer_class = HealthProgramLocumNeedAdminSerializer
    filterset_fields = ["program", "locum_job"]
    ordering_fields = ["date_created"]
    facet_fields = ["program"]


class InterventionTypeAdminViewSet(AdminReadOnlyViewSet):
    queryset = ProgramInterventionType.objects.all()
    serializer_class = ProgramInterventionTypeSerializer
    search_fields = ["name"]
    filterset_fields = ["default"]
    ordering_fields = ["name"]
    facet_fields = ["default"]


class HealthProgramInvitationAdminSerializer(serializers.ModelSerializer):
    program_name = serializers.CharField(source="program.program_name", read_only=True, default=None)

    class Meta:
        model = HealthProgramInvitation
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at")


class HealthProgramInvitationAdminViewSet(AdminReadOnlyViewSet):
    queryset = HealthProgramInvitation.objects.select_related("program", "invited_to").all()
    serializer_class = HealthProgramInvitationAdminSerializer
    search_fields = ["program__program_name"]
    filterset_fields = ["program", "status", "source"]
    ordering_fields = ["created_at"]
    facet_fields = ["program", "status", "source"]


class InterventionFieldAdminViewSet(AdminReadOnlyViewSet):
    queryset = InterventionField.objects.select_related("intervention").all()
    serializer_class = InterventionFieldSerializer
    search_fields = ["name"]
    filterset_fields = ["intervention", "field_type", "section"]
    ordering_fields = ["order"]
    facet_fields = ["intervention", "field_type", "section"]


class InterventionFieldOptionAdminViewSet(AdminReadOnlyViewSet):
    queryset = InterventionFieldOption.objects.select_related("field").all()
    serializer_class = InterventionFieldOptionSerializer
    search_fields = ["option"]
    filterset_fields = ["field"]
    ordering_fields = ["id"]
    facet_fields = ["field"]


class InterventionResponseValueAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = InterventionResponseValue
        fields = "__all__"
        read_only_fields = ("id", "date_created", "last_updated")


class InterventionResponseValueAdminViewSet(AdminReadOnlyViewSet):
    queryset = InterventionResponseValue.objects.select_related("response", "field").all()
    serializer_class = InterventionResponseValueAdminSerializer
    filterset_fields = ["response", "field"]
    ordering_fields = ["recorded_at", "date_created"]
    facet_fields = ["response", "field"]


class InterventionTemplateAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = InterventionTemplate
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at")


class InterventionTemplateAdminViewSet(AdminReadOnlyViewSet):
    queryset = InterventionTemplate.objects.select_related("organization").all()
    serializer_class = InterventionTemplateAdminSerializer
    search_fields = ["name"]
    filterset_fields = ["organization", "intervention_type", "is_platform_default", "is_active"]
    ordering_fields = ["created_at"]
    facet_fields = ["organization", "is_platform_default", "is_active"]


class InterventionTemplateFieldAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = InterventionTemplateField
        fields = "__all__"
        read_only_fields = ("id",)


class InterventionTemplateFieldAdminViewSet(AdminReadOnlyViewSet):
    queryset = InterventionTemplateField.objects.select_related("template").all()
    serializer_class = InterventionTemplateFieldAdminSerializer
    search_fields = ["name"]
    filterset_fields = ["template", "field_type", "section"]
    ordering_fields = ["order"]
    facet_fields = ["template", "field_type", "section"]


class SurveyTypeAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = SurveyType
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at")


class SurveyTypeAdminViewSet(AdminReadOnlyViewSet):
    queryset = SurveyType.objects.all()
    serializer_class = SurveyTypeAdminSerializer
    search_fields = ["name"]
    filterset_fields = ["default"]
    ordering_fields = ["name"]
    facet_fields = ["default"]


class SurveyQuestionAdminViewSet(AdminModelViewSet):
    queryset = SurveyQuestion.objects.select_related("survey").all()
    serializer_class = SurveyQuestionSerializer
    search_fields = ["question"]
    filterset_fields = ["survey", "question_type", "required"]
    ordering_fields = ["date_created"]
    facet_fields = ["survey", "question_type", "required"]


class SurveyQuestionOptionAdminViewSet(AdminModelViewSet):
    queryset = SurveyQuestionOption.objects.select_related("question").all()
    serializer_class = SurveyQuesitonOptionSerializer
    search_fields = ["option"]
    filterset_fields = ["question"]
    ordering_fields = ["id"]
    facet_fields = ["question"]


class SurveyResponseAnswerAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = SurveyResponseAnswers
        fields = "__all__"
        read_only_fields = ("id", "date_created", "last_updated")


class SurveyResponseAnswerAdminViewSet(AdminReadOnlyViewSet):
    queryset = SurveyResponseAnswers.objects.select_related("response", "question").all()
    serializer_class = SurveyResponseAnswerAdminSerializer
    filterset_fields = ["response", "question"]
    ordering_fields = ["date_created"]
    facet_fields = ["response", "question"]


class BulkSurveyUploadAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = BulkSurveyUpload
        fields = "__all__"
        read_only_fields = ("id",)


class BulkSurveyUploadAdminViewSet(AdminReadOnlyViewSet):
    queryset = BulkSurveyUpload.objects.select_related("survey", "uploaded_by").all()
    serializer_class = BulkSurveyUploadAdminSerializer
    search_fields = ["file_name"]
    filterset_fields = ["status", "survey"]
    ordering_fields = ["uploaded_at"]
    facet_fields = ["survey", "status"]


def register(router):
    router.register("organizations", OrganizationAdminViewSet, basename="admin-organizations")
    router.register("organization-staff", OrganizationStaffAdminViewSet, basename="admin-organization-staff")
    router.register("organization-files", OrganizationFilesAdminViewSet, basename="admin-organization-files")
    router.register("health-programs", HealthProgramAdminViewSet, basename="admin-health-programs")
    router.register("participants", ParticipantAdminViewSet, basename="admin-participants")
    router.register("interventions", InterventionAdminViewSet, basename="admin-interventions")
    router.register("intervention-responses", InterventionResponseAdminViewSet, basename="admin-intervention-responses")
    router.register("bulk-intervention-uploads", BulkInterventionUploadAdminViewSet, basename="admin-bulk-intervention-uploads")
    router.register("survey-types", SurveyTypeAdminViewSet, basename="admin-survey-types")
    router.register("survey-questions", SurveyQuestionAdminViewSet, basename="admin-survey-questions")
    router.register("survey-question-options", SurveyQuestionOptionAdminViewSet, basename="admin-survey-question-options")
    router.register("survey-response-answers", SurveyResponseAnswerAdminViewSet, basename="admin-survey-response-answers")
    router.register("bulk-survey-uploads", BulkSurveyUploadAdminViewSet, basename="admin-bulk-survey-uploads")
    router.register("program-catalogs", ProgramCatalogAdminViewSet, basename="admin-program-catalogs")
    router.register("surveys", SurveyAdminViewSet, basename="admin-surveys")
    router.register("survey-responses", SurveyResponseAdminViewSet, basename="admin-survey-responses")
    router.register("locum-jobs", LocumJobAdminViewSet, basename="admin-locum-jobs")
    router.register("locum-applications", LocumApplicationAdminViewSet, basename="admin-locum-applications")
    router.register("issued-certificates", IssuedCertificateAdminViewSet, basename="admin-issued-certificates")
    router.register("certificate-templates", CertificateTemplateAdminViewSet, basename="admin-certificate-templates")
    router.register("locum-job-roles", LocumJobRoleAdminViewSet, basename="admin-locum-job-roles")
    router.register("program-partners", HealthProgramPartnersAdminViewSet, basename="admin-program-partners")
    router.register("program-locum-needs", ProgramLocumNeedAdminViewSet, basename="admin-program-locum-needs")
    router.register("intervention-types", InterventionTypeAdminViewSet, basename="admin-intervention-types")
    router.register("program-invitations", HealthProgramInvitationAdminViewSet, basename="admin-program-invitations")
    router.register("intervention-fields", InterventionFieldAdminViewSet, basename="admin-intervention-fields")
    router.register("intervention-field-options", InterventionFieldOptionAdminViewSet, basename="admin-intervention-field-options")
    router.register("intervention-response-values", InterventionResponseValueAdminViewSet, basename="admin-intervention-response-values")
    router.register("intervention-templates", InterventionTemplateAdminViewSet, basename="admin-intervention-templates")
    router.register("intervention-template-fields", InterventionTemplateFieldAdminViewSet, basename="admin-intervention-template-fields")


EXTRA_URLS = []
