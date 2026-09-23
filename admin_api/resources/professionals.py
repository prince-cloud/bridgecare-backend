"""Admin API resources for the professionals app."""
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.response import Response

from professionals.models import (
    ProfessionalProfile, Appointment, Profession,
    Specialization, LicenceIssueAuthority,
    Availability, EducationHistory, AvailabilityBlock, BreakPeriod,
)
from professionals.serializers import (
    ProfessionalProfileSerializer,
    AppointmentSerializer,
    ProfessionsSerializer,
    SpecializationSerializer,
    LicenceIssueAuthoritySerializer,
    AvailabilitySerializer,
    AvailabilityBlockSerializer,
    BreakPeriodSerializer,
    EducationHistorySerializer,
)
from admin_api.base import AdminModelViewSet, AdminReadOnlyViewSet


class ProfessionalAdminSerializer(serializers.ModelSerializer):
    """Admin view of a professional with a flat user reference — the app
    serializer nests the whole user object, which the admin portal's
    foreign-key widget can't use."""

    user_name = serializers.SerializerMethodField()

    class Meta:
        model = ProfessionalProfile
        fields = [
            "id", "user", "user_name", "profession", "specialization",
            "facility_affiliation", "license_number", "license_expiry_date",
            "years_of_experience", "is_verified", "is_student",
            "education_status", "created_at", "updated_at",
        ]

    def get_user_name(self, obj):
        u = obj.user
        if not u:
            return None
        name = " ".join(x for x in [u.first_name, u.last_name] if x)
        return name or u.email


class ProfessionalAdminViewSet(AdminModelViewSet):
    queryset = ProfessionalProfile.objects.select_related(
        "user", "profession", "specialization"
    ).all()
    serializer_class = ProfessionalAdminSerializer
    search_fields = ["user__first_name", "user__last_name", "user__email"]
    filterset_fields = ["profession", "specialization", "is_verified", "is_student"]
    ordering_fields = ["created_at"]
    facet_fields = ["profession", "is_verified"]

    @action(detail=True, methods=["post"])
    def verify(self, request, pk=None):
        p = self.get_object(); p.is_verified = True; p.save()
        return Response(ProfessionalAdminSerializer(p).data)

    @action(detail=True, methods=["post"])
    def unverify(self, request, pk=None):
        p = self.get_object(); p.is_verified = False; p.save()
        return Response(ProfessionalAdminSerializer(p).data)


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




class SpecializationAdminViewSet(AdminReadOnlyViewSet):
    queryset = Specialization.objects.all()
    serializer_class = SpecializationSerializer
    search_fields = ["name"]
    filterset_fields = ["is_active"]
    ordering_fields = ["name"]
    facet_fields = ["is_active"]


class LicenceAuthorityAdminViewSet(AdminReadOnlyViewSet):
    queryset = LicenceIssueAuthority.objects.all()
    serializer_class = LicenceIssueAuthoritySerializer
    search_fields = ["name"]
    filterset_fields = ["is_active"]
    ordering_fields = ["name"]
    facet_fields = ["is_active"]


class AvailabilityAdminViewSet(AdminReadOnlyViewSet):
    queryset = Availability.objects.select_related("provider__user").all()
    serializer_class = AvailabilitySerializer
    search_fields = ["provider__user__email"]
    filterset_fields = ["provider", "patient_visit_availability", "provider_visit_availability", "telehealth_availability"]
    ordering_fields = ["created_at"]
    facet_fields = ["provider", "patient_visit_availability", "telehealth_availability"]


class EducationHistoryAdminViewSet(AdminReadOnlyViewSet):
    queryset = EducationHistory.objects.select_related("professional_profile").all()
    serializer_class = EducationHistorySerializer
    search_fields = ["education_institution", "professional_profile__user__email"]
    filterset_fields = ["professional_profile", "education_level", "is_current_education"]
    ordering_fields = ["created_at"]
    facet_fields = ["education_level", "is_current_education"]


class AvailabilityBlockAdminViewSet(AdminReadOnlyViewSet):
    queryset = AvailabilityBlock.objects.select_related("provider").all()
    serializer_class = AvailabilityBlockSerializer
    filterset_fields = ["provider", "day_of_week"]
    ordering_fields = ["day_of_week", "start_time"]
    facet_fields = ["provider", "day_of_week"]


class BreakPeriodAdminViewSet(AdminReadOnlyViewSet):
    queryset = BreakPeriod.objects.select_related("availability").all()
    serializer_class = BreakPeriodSerializer
    filterset_fields = ["availability"]
    ordering_fields = ["break_start"]
    facet_fields = ["availability"]


def register(router):
    router.register("professionals", ProfessionalAdminViewSet, basename="admin-professionals")
    router.register("professional-appointments", ProfessionalAppointmentAdminViewSet, basename="admin-professional-appointments")
    router.register("professional-lookups", ProfessionalLookupAdminViewSet, basename="admin-professional-lookups")
    router.register("specializations", SpecializationAdminViewSet, basename="admin-specializations")
    router.register("licence-authorities", LicenceAuthorityAdminViewSet, basename="admin-licence-authorities")
    router.register("availabilities", AvailabilityAdminViewSet, basename="admin-availabilities")
    router.register("education-histories", EducationHistoryAdminViewSet, basename="admin-education-histories")
    router.register("availability-blocks", AvailabilityBlockAdminViewSet, basename="admin-availability-blocks")
    router.register("break-periods", BreakPeriodAdminViewSet, basename="admin-break-periods")


EXTRA_URLS = []
