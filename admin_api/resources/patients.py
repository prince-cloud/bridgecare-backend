"""Admin API resources for the patients app."""
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.response import Response

from patients.models import (
    PatientProfile,
    Visitation,
    PatientAccess,
    FacilityPatientAccess,
    Diagnosis,
    Vitals,
    Prescription,
    Allergy,
    Notes,
    MedicalHistory,
)
from patients.serializers import (
    PatientProfileSerializer,
    PatientProfileListSerializer,
    VisitationSerializer,
    VisitationDetailSerializer,
    DiagnosisSerializer,
    VitalsSerializer,
    PrescriptionSerializer,
    AllergySerializer,
    NotesSerializer,
    MedicalHistorySerializer,
)
from admin_api.base import AdminModelViewSet, AdminReadOnlyViewSet


class PatientAccessAdminSerializer(serializers.ModelSerializer):
    patient_name = serializers.SerializerMethodField()
    professional_name = serializers.SerializerMethodField()

    class Meta:
        model = PatientAccess
        fields = ["id", "patient", "patient_name", "professional_name", "is_active", "created_at"]

    def get_patient_name(self, obj):
        p = getattr(obj, "patient", None)
        if not p:
            return None
        return f"{getattr(p, 'first_name', '')} {getattr(p, 'surname', '')}".strip()

    def get_professional_name(self, obj):
        hp = getattr(obj, "health_professional", None)
        u = getattr(hp, "user", None) if hp else None
        return (u.get_full_name() if u else None) or None


class PatientAdminViewSet(AdminModelViewSet):
    queryset = PatientProfile.objects.select_related("user").all()
    serializer_class = PatientProfileSerializer
    search_fields = ["first_name", "surname", "email", "phone_number"]
    filterset_fields = ["gender", "blood_type"]
    ordering_fields = ["date_created", "first_name"]
    facet_fields = ["gender", "blood_type"]

    def get_serializer_class(self):
        # The list serializer omits clinical fields (blood type, emergency
        # contact) the admin portal shows — always use the full one.
        return PatientProfileSerializer


class VisitationAdminViewSet(AdminModelViewSet):
    queryset = Visitation.objects.select_related("facility", "patient").all()
    serializer_class = VisitationSerializer
    search_fields = ["title", "patient__first_name", "patient__surname"]
    filterset_fields = ["status", "facility", "patient"]
    ordering_fields = ["date_created"]
    facet_fields = ["facility", "status"]

    def get_serializer_class(self):
        # The detail serializer is a slim clinical shape (no title/status/
        # facility) meant for the app screen — the portal needs the full one.
        return VisitationSerializer


class PatientAccessGrantAdminViewSet(AdminReadOnlyViewSet):
    queryset = PatientAccess.objects.select_related("patient", "health_professional").all()
    serializer_class = PatientAccessAdminSerializer
    search_fields = ["patient__first_name", "patient__surname", "health_professional__user__email"]
    filterset_fields = ["patient", "health_professional", "is_active"]
    ordering_fields = ["created_at"]
    facet_fields = ["patient", "health_professional", "is_active"]

    @action(detail=True, methods=["post"])
    def revoke(self, request, pk=None):
        grant = self.get_object(); grant.is_active = False; grant.save()
        return Response(PatientAccessAdminSerializer(grant).data)


class FacilityPatientAccessAdminSerializer(serializers.ModelSerializer):
    facility_name = serializers.CharField(source="facility.name", read_only=True, default=None)

    class Meta:
        model = FacilityPatientAccess
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at")


class FacilityPatientAccessAdminViewSet(AdminReadOnlyViewSet):
    queryset = FacilityPatientAccess.objects.select_related("facility", "patient").all()
    serializer_class = FacilityPatientAccessAdminSerializer
    search_fields = ["patient__first_name", "patient__surname"]
    filterset_fields = ["facility", "patient", "is_active"]
    ordering_fields = ["created_at"]
    facet_fields = ["facility", "patient", "is_active"]


class DiagnosisAdminViewSet(AdminModelViewSet):
    queryset = Diagnosis.objects.select_related("visitation").all()
    serializer_class = DiagnosisSerializer
    search_fields = ["diagnosis"]
    filterset_fields = ["visitation"]
    ordering_fields = ["date_created"]
    facet_fields = ["visitation"]


class VitalsAdminViewSet(AdminModelViewSet):
    queryset = Vitals.objects.select_related("visitation").all()
    serializer_class = VitalsSerializer
    search_fields = ["label"]
    filterset_fields = ["visitation"]
    ordering_fields = ["recorded_at", "date_created"]
    facet_fields = ["visitation"]


class PrescriptionAdminViewSet(AdminModelViewSet):
    queryset = Prescription.objects.select_related("visitation").all()
    serializer_class = PrescriptionSerializer
    search_fields = ["medication"]
    filterset_fields = ["visitation"]
    ordering_fields = ["date_created"]
    facet_fields = ["visitation"]


class AllergyAdminViewSet(AdminModelViewSet):
    queryset = Allergy.objects.select_related("patient").all()
    serializer_class = AllergySerializer
    search_fields = ["allergy", "patient__first_name", "patient__surname"]
    filterset_fields = ["patient", "allergy_severity"]
    ordering_fields = ["date_created"]
    facet_fields = ["patient", "allergy_severity"]


class NotesAdminViewSet(AdminModelViewSet):
    queryset = Notes.objects.select_related("visitation", "issued_by").all()
    serializer_class = NotesSerializer
    search_fields = ["note"]
    filterset_fields = ["visitation", "issued_by"]
    ordering_fields = ["date_created"]
    facet_fields = ["visitation", "issued_by"]


class MedicalHistoryAdminViewSet(AdminModelViewSet):
    queryset = MedicalHistory.objects.select_related("patient").all()
    serializer_class = MedicalHistorySerializer
    search_fields = ["name", "patient__first_name", "patient__surname"]
    filterset_fields = ["patient", "history_type"]
    ordering_fields = ["date_created"]
    facet_fields = ["patient", "history_type"]


def register(router):
    router.register("patients", PatientAdminViewSet, basename="admin-patients")
    router.register("visitations", VisitationAdminViewSet, basename="admin-visitations")
    router.register("patient-access-grants", PatientAccessGrantAdminViewSet, basename="admin-patient-access-grants")
    router.register("facility-patient-access", FacilityPatientAccessAdminViewSet, basename="admin-facility-patient-access")
    router.register("diagnoses", DiagnosisAdminViewSet, basename="admin-diagnoses")
    router.register("vitals", VitalsAdminViewSet, basename="admin-vitals")
    router.register("prescriptions", PrescriptionAdminViewSet, basename="admin-prescriptions")
    router.register("allergies", AllergyAdminViewSet, basename="admin-allergies")
    router.register("clinical-notes", NotesAdminViewSet, basename="admin-clinical-notes")
    router.register("medical-histories", MedicalHistoryAdminViewSet, basename="admin-medical-histories")


EXTRA_URLS = []
