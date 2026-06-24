"""Admin API resources for the professionals app."""
from rest_framework.decorators import action
from rest_framework.response import Response

from professionals.models import ProfessionalProfile, Appointment, Profession
from professionals.serializers import (
    ProfessionalProfileSerializer,
    AppointmentSerializer,
    ProfessionsSerializer,
)
from admin_api.base import AdminModelViewSet, AdminReadOnlyViewSet


class ProfessionalAdminViewSet(AdminModelViewSet):
    queryset = ProfessionalProfile.objects.select_related(
        "user", "profession", "specialization"
    ).all()
    serializer_class = ProfessionalProfileSerializer
    search_fields = ["user__first_name", "user__last_name", "user__email"]
    filterset_fields = ["profession", "specialization", "is_verified", "is_student"]
    ordering_fields = ["created_at"]

    @action(detail=True, methods=["post"])
    def verify(self, request, pk=None):
        p = self.get_object(); p.is_verified = True; p.save()
        return Response(ProfessionalProfileSerializer(p, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def unverify(self, request, pk=None):
        p = self.get_object(); p.is_verified = False; p.save()
        return Response(ProfessionalProfileSerializer(p, context={"request": request}).data)


class ProfessionalAppointmentAdminViewSet(AdminReadOnlyViewSet):
    queryset = Appointment.objects.all()
    serializer_class = AppointmentSerializer
    filterset_fields = ["status", "appointment_type"]
    ordering_fields = ["date", "created_at"]


class ProfessionalLookupAdminViewSet(AdminModelViewSet):
    queryset = Profession.objects.all()
    serializer_class = ProfessionsSerializer
    search_fields = ["name"]
    filterset_fields = ["is_active"]
    ordering_fields = ["name"]


def register(router):
    router.register("professionals", ProfessionalAdminViewSet, basename="admin-professionals")
    router.register("professional-appointments", ProfessionalAppointmentAdminViewSet, basename="admin-professional-appointments")
    router.register("professional-lookups", ProfessionalLookupAdminViewSet, basename="admin-professional-lookups")


EXTRA_URLS = []
