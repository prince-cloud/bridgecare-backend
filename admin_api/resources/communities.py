"""Admin API resources for the communities app."""
from rest_framework.decorators import action
from rest_framework.response import Response

from communities.models import (
    Organization,
    Staff,
    OrganizationFiles,
    HealthProgram,
    HealthProgramType,
    ProgramIntervention,
    InterventionResponse,
    BulkInterventionUpload,
    Survey,
    SurveyResponse,
    LocumJob,
    LocumJobApplication,
    IssuedCertificate,
    CertificateTemplate,
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
)
from admin_api.base import AdminModelViewSet, AdminReadOnlyViewSet


class OrganizationAdminViewSet(AdminModelViewSet):
    queryset = Organization.objects.select_related("user").all()
    serializer_class = OrganizationSerializer
    search_fields = ["organization_name", "organization_email", "registration_number"]
    filterset_fields = ["organization_type", "verified"]
    ordering_fields = ["created_at", "organization_name"]

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
    filterset_fields = ["document_type", "organization"]
    ordering_fields = ["created_at"]


class HealthProgramAdminViewSet(AdminModelViewSet):
    queryset = HealthProgram.objects.select_related("organization", "program_type").all()
    serializer_class = HealthProgramSerializer
    search_fields = ["program_name"]
    filterset_fields = ["status", "program_type", "organization"]
    ordering_fields = ["created_at", "start_date"]

    def get_serializer_class(self):
        if self.action == "list":
            return ShortHealthProgramSerializer
        return HealthProgramSerializer

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


class InterventionResponseAdminViewSet(AdminReadOnlyViewSet):
    queryset = InterventionResponse.objects.select_related("intervention", "participant").all()
    serializer_class = InterventionResponseSerializer
    filterset_fields = ["intervention"]
    ordering_fields = ["date_created"]


class BulkInterventionUploadAdminViewSet(AdminReadOnlyViewSet):
    queryset = BulkInterventionUpload.objects.all()
    serializer_class = BulkInterventionUploadSerializer
    filterset_fields = ["status", "program"]
    ordering_fields = ["uploaded_at"]


class ProgramCatalogAdminViewSet(AdminModelViewSet):
    queryset = HealthProgramType.objects.all()
    serializer_class = HealthProgramTypeSerializer
    search_fields = ["name"]
    ordering_fields = ["name"]


class SurveyAdminViewSet(AdminModelViewSet):
    queryset = Survey.objects.all()
    serializer_class = SurveyDetailSerializer
    search_fields = ["title"]
    filterset_fields = ["active"]
    ordering_fields = ["date_created", "end_date"]

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
    filterset_fields = ["survey"]
    ordering_fields = ["date_created"]


class LocumJobAdminViewSet(AdminModelViewSet):
    queryset = LocumJob.objects.select_related("organization", "role").all()
    serializer_class = LocumJobDetailSerializer
    search_fields = ["title"]
    filterset_fields = ["job_type", "is_active", "approved", "organization", "role"]
    ordering_fields = ["created_at"]

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
    queryset = LocumJobApplication.objects.select_related("job").all()
    serializer_class = LocumJobApplicationSerializer
    filterset_fields = ["status", "job"]
    ordering_fields = ["applied_at"]


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


def register(router):
    router.register("organizations", OrganizationAdminViewSet, basename="admin-organizations")
    router.register("organization-staff", OrganizationStaffAdminViewSet, basename="admin-organization-staff")
    router.register("organization-files", OrganizationFilesAdminViewSet, basename="admin-organization-files")
    router.register("health-programs", HealthProgramAdminViewSet, basename="admin-health-programs")
    router.register("interventions", InterventionAdminViewSet, basename="admin-interventions")
    router.register("intervention-responses", InterventionResponseAdminViewSet, basename="admin-intervention-responses")
    router.register("bulk-intervention-uploads", BulkInterventionUploadAdminViewSet, basename="admin-bulk-intervention-uploads")
    router.register("program-catalogs", ProgramCatalogAdminViewSet, basename="admin-program-catalogs")
    router.register("surveys", SurveyAdminViewSet, basename="admin-surveys")
    router.register("survey-responses", SurveyResponseAdminViewSet, basename="admin-survey-responses")
    router.register("locum-jobs", LocumJobAdminViewSet, basename="admin-locum-jobs")
    router.register("locum-applications", LocumApplicationAdminViewSet, basename="admin-locum-applications")
    router.register("issued-certificates", IssuedCertificateAdminViewSet, basename="admin-issued-certificates")
    router.register("certificate-templates", CertificateTemplateAdminViewSet, basename="admin-certificate-templates")


EXTRA_URLS = []
