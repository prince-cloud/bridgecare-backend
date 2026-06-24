"""Admin API resources for the partners app."""
from rest_framework.decorators import action
from rest_framework.response import Response

from partners.models import (
    PartnerProfile,
    Subsidy,
    ProgramPartnershipRequest,
    ProgramMonitor,
)
from partners.serializers import (
    PartnerProfileSerializer,
    SubsidySerializer,
    ProgramPartnershipRequestSerializer,
    ProgramMonitorSerializer,
    ProgramMonitorDetailSerializer,
)
from admin_api.base import AdminModelViewSet, AdminReadOnlyViewSet


class PartnerAdminViewSet(AdminModelViewSet):
    queryset = PartnerProfile.objects.select_related("user").all()
    serializer_class = PartnerProfileSerializer
    search_fields = ["organization_name", "organization_email"]
    filterset_fields = ["organization_type", "partnership_type", "is_verified"]
    ordering_fields = ["created_at", "organization_name"]

    @action(detail=True, methods=["post"])
    def verify(self, request, pk=None):
        p = self.get_object(); p.is_verified = True; p.save()
        return Response(PartnerProfileSerializer(p).data)

    @action(detail=True, methods=["post"])
    def unverify(self, request, pk=None):
        p = self.get_object(); p.is_verified = False; p.save()
        return Response(PartnerProfileSerializer(p).data)


class SubsidyAdminViewSet(AdminModelViewSet):
    queryset = Subsidy.objects.select_related("partner").all()
    serializer_class = SubsidySerializer
    filterset_fields = ["status", "subsidy_type", "partner"]
    ordering_fields = ["start_date", "created_at"]

    def _set_status(self, value):
        s = self.get_object(); s.status = value; s.save()
        return Response(SubsidySerializer(s).data)

    @action(detail=True, methods=["post"])
    def pause(self, request, pk=None):
        return self._set_status("paused")

    @action(detail=True, methods=["post"])
    def resume(self, request, pk=None):
        return self._set_status("active")

    @action(detail=True, methods=["post"], url_path="mark-exhausted")
    def mark_exhausted(self, request, pk=None):
        return self._set_status("exhausted")


class PartnershipRequestAdminViewSet(AdminReadOnlyViewSet):
    queryset = ProgramPartnershipRequest.objects.all()
    serializer_class = ProgramPartnershipRequestSerializer
    filterset_fields = ["status", "direction"]
    ordering_fields = ["created_at"]

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        r = self.get_object(); r.status = "approved"; r.save()
        return Response(ProgramPartnershipRequestSerializer(r).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        r = self.get_object(); r.status = "rejected"; r.save()
        return Response(ProgramPartnershipRequestSerializer(r).data)


class ProgramMonitorAdminViewSet(AdminReadOnlyViewSet):
    queryset = ProgramMonitor.objects.select_related("partner").all()
    serializer_class = ProgramMonitorSerializer
    filterset_fields = ["is_active", "partner"]
    ordering_fields = ["created_at"]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ProgramMonitorDetailSerializer
        return ProgramMonitorSerializer


def register(router):
    router.register("partners", PartnerAdminViewSet, basename="admin-partners")
    router.register("subsidies", SubsidyAdminViewSet, basename="admin-subsidies")
    router.register("partnership-requests", PartnershipRequestAdminViewSet, basename="admin-partnership-requests")
    router.register("program-monitors", ProgramMonitorAdminViewSet, basename="admin-program-monitors")


EXTRA_URLS = []
