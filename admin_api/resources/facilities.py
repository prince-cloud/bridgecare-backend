"""Admin API resources for the facilities app."""
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.response import Response

from facilities.models import (
    FacilityProfile,
    FacilityStaff,
    StaffInvitation,
    Ward,
    Bed,
    FacilityAppointment,
    LabTest,
    Locum,
)
from facilities.serializers import (
    FacilityProfileSerializer,
    FacilityStaffSerializer,
    StaffInvitationSerializer,
    WardSerializer,
    WardListSerializer,
    BedSerializer,
    FacilityAppointmentSerializer,
    LabTestSerializer,
    LocumSerializer,
)
from admin_api.base import AdminModelViewSet, AdminReadOnlyViewSet


class FacilityAdminViewSet(AdminModelViewSet):
    queryset = FacilityProfile.objects.select_related("user").all()
    serializer_class = FacilityProfileSerializer
    search_fields = ["name", "email", "address"]
    filterset_fields = ["facility_type", "region", "district", "is_active"]
    ordering_fields = ["created_at", "name"]
    facet_fields = ["facility_type", "region", "is_active"]


class FacilityStaffAdminSerializer(serializers.ModelSerializer):
    """Admin write view — the app serializer makes the facility FK read-only."""

    facility_name = serializers.CharField(source="facility.name", read_only=True, default=None)

    class Meta:
        model = FacilityStaff
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at")


class WardAdminSerializer(serializers.ModelSerializer):
    """Admin write view — the app serializer makes the facility FK read-only."""

    class Meta:
        model = Ward
        fields = ("id", "facility", "name", "ward_type", "description", "capacity", "is_active", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")


class FacilityStaffAdminViewSet(AdminModelViewSet):
    queryset = FacilityStaff.objects.select_related("facility", "user").all()
    serializer_class = FacilityStaffAdminSerializer
    search_fields = ["full_name", "email", "employee_id"]
    filterset_fields = ["facility", "profession", "department", "is_active"]
    ordering_fields = ["created_at"]
    facet_fields = ["facility", "profession", "is_active"]

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        s = self.get_object(); s.is_active = True; s.save()
        return Response(FacilityStaffSerializer(s).data)

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        s = self.get_object(); s.is_active = False; s.save()
        return Response(FacilityStaffSerializer(s).data)


class StaffInvitationAdminViewSet(AdminReadOnlyViewSet):
    queryset = StaffInvitation.objects.select_related("facility").all()
    serializer_class = StaffInvitationSerializer
    search_fields = ["full_name", "email"]
    filterset_fields = ["status", "facility", "profession"]
    ordering_fields = ["created_at"]
    facet_fields = ["facility", "status", "profession"]


class WardAdminViewSet(AdminModelViewSet):
    queryset = Ward.objects.select_related("facility").all()
    serializer_class = WardAdminSerializer
    search_fields = ["name"]
    filterset_fields = ["facility", "ward_type", "is_active"]
    ordering_fields = ["created_at", "name"]
    facet_fields = ["facility", "ward_type", "is_active"]

    def get_serializer_class(self):
        if self.action == "list":
            return WardListSerializer
        return WardAdminSerializer


class BedAdminViewSet(AdminModelViewSet):
    queryset = Bed.objects.select_related("ward", "patient").all()
    serializer_class = BedSerializer
    search_fields = ["bed_number"]
    filterset_fields = ["status", "ward"]
    ordering_fields = ["created_at"]
    facet_fields = ["ward", "status"]

    @action(detail=True, methods=["post"], url_path="set-maintenance")
    def set_maintenance(self, request, pk=None):
        b = self.get_object(); b.status = "maintenance"; b.save()
        return Response(BedSerializer(b).data)

    @action(detail=True, methods=["post"], url_path="set-available")
    def set_available(self, request, pk=None):
        b = self.get_object(); b.status = "available"; b.save()
        return Response(BedSerializer(b).data)


class FacilityAppointmentAdminViewSet(AdminModelViewSet):
    queryset = FacilityAppointment.objects.select_related("facility", "patient", "provider").all()
    serializer_class = FacilityAppointmentSerializer
    search_fields = ["reason", "patient__first_name", "patient__surname"]
    filterset_fields = ["status", "appointment_type", "facility", "patient"]
    ordering_fields = ["date", "created_at"]
    facet_fields = ["facility", "status"]


class LabTestAdminViewSet(AdminReadOnlyViewSet):
    queryset = LabTest.objects.select_related("facility", "patient").all()
    serializer_class = LabTestSerializer
    search_fields = ["test_name", "patient__first_name", "patient__surname"]
    filterset_fields = ["status", "facility", "test_category"]
    ordering_fields = ["created_at"]
    facet_fields = ["facility", "status", "test_category"]


class LocumWorkerAdminViewSet(AdminModelViewSet):
    queryset = Locum.objects.select_related("user").all()
    serializer_class = LocumSerializer
    search_fields = ["full_name", "email"]
    filterset_fields = ["profession", "is_available", "region", "district"]
    ordering_fields = ["created_at"]
    facet_fields = ["profession", "is_available", "region"]


def register(router):
    router.register("facilities", FacilityAdminViewSet, basename="admin-facilities")
    router.register("facility-staff", FacilityStaffAdminViewSet, basename="admin-facility-staff")
    router.register("staff-invitations", StaffInvitationAdminViewSet, basename="admin-staff-invitations")
    router.register("wards", WardAdminViewSet, basename="admin-wards")
    router.register("beds", BedAdminViewSet, basename="admin-beds")
    router.register("facility-appointments", FacilityAppointmentAdminViewSet, basename="admin-facility-appointments")
    router.register("lab-tests", LabTestAdminViewSet, basename="admin-lab-tests")
    router.register("locum-workers", LocumWorkerAdminViewSet, basename="admin-locum-workers")


EXTRA_URLS = []
