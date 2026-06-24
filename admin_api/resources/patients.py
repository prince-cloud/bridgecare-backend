"""Admin API resources for the patients app."""
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.response import Response

from patients.models import PatientProfile, Visitation, PatientAccess
from patients.serializers import (
    PatientProfileSerializer,
    PatientProfileListSerializer,
    VisitationSerializer,
    VisitationDetailSerializer,
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
    filterset_fields = ["gender"]
    ordering_fields = ["date_created"]

    def get_serializer_class(self):
        if self.action == "list":
            return PatientProfileListSerializer
        return PatientProfileSerializer


class VisitationAdminViewSet(AdminReadOnlyViewSet):
    queryset = Visitation.objects.select_related("facility").all()
    serializer_class = VisitationSerializer
    filterset_fields = ["status", "facility"]
    ordering_fields = ["date_created"]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return VisitationDetailSerializer
        return VisitationSerializer


class PatientAccessGrantAdminViewSet(AdminReadOnlyViewSet):
    queryset = PatientAccess.objects.select_related("patient", "health_professional").all()
    serializer_class = PatientAccessAdminSerializer
    filterset_fields = ["is_active"]
    ordering_fields = ["created_at"]

    @action(detail=True, methods=["post"])
    def revoke(self, request, pk=None):
        grant = self.get_object(); grant.is_active = False; grant.save()
        return Response(PatientAccessAdminSerializer(grant).data)


def register(router):
    router.register("patients", PatientAdminViewSet, basename="admin-patients")
    router.register("visitations", VisitationAdminViewSet, basename="admin-visitations")
    router.register("patient-access-grants", PatientAccessGrantAdminViewSet, basename="admin-patient-access-grants")


EXTRA_URLS = []
