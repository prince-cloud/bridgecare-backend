"""Aggregation endpoints powering the admin dashboards."""
from django.urls import path
from rest_framework.response import Response
from rest_framework.views import APIView

from .permissions import IsPlatformAdmin


class AdminOverviewView(APIView):
    """Platform-wide counts: users, entities, and the verification backlog."""

    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        from accounts.models import CustomUser
        from communities.models import Organization, HealthProgram
        from facilities.models import FacilityProfile
        from professionals.models import ProfessionalProfile
        from pharmacies.models import PharmacyProfile, Order
        from partners.models import PartnerProfile
        from patients.models import PatientProfile

        return Response(
            {
                "users": {
                    "total": CustomUser.objects.count(),
                    "verified": CustomUser.objects.filter(is_verified=True).count(),
                    "active": CustomUser.objects.filter(is_active=True).count(),
                    "locked": CustomUser.objects.filter(
                        account_locked_until__isnull=False
                    ).count(),
                },
                "entities": {
                    "organizations": Organization.objects.count(),
                    "facilities": FacilityProfile.objects.count(),
                    "professionals": ProfessionalProfile.objects.count(),
                    "pharmacies": PharmacyProfile.objects.count(),
                    "partners": PartnerProfile.objects.count(),
                    "patients": PatientProfile.objects.count(),
                },
                "pending_verifications": {
                    "organizations": Organization.objects.filter(verified=False).count(),
                    "professionals": ProfessionalProfile.objects.filter(
                        is_verified=False
                    ).count(),
                    "pharmacies": PharmacyProfile.objects.filter(
                        is_verified=False
                    ).count(),
                    "partners": PartnerProfile.objects.filter(is_verified=False).count(),
                },
                "commerce": {
                    "total_orders": Order.objects.count(),
                    "health_programs": HealthProgram.objects.count(),
                },
            }
        )


class AdminVerificationsView(APIView):
    """The approval/verification backlog with the actual pending items so an
    operator can act on them directly. Each item carries the resource `path`
    and `action` to call (e.g. POST /admin-api/organizations/<id>/verify/)."""

    permission_classes = [IsPlatformAdmin]
    LIMIT = 50

    def get(self, request):
        from communities.models import Organization
        from professionals.models import ProfessionalProfile
        from pharmacies.models import PharmacyProfile
        from partners.models import PartnerProfile

        def items(qs, path, name_fn):
            out = []
            for obj in qs[: self.LIMIT]:
                out.append({"id": str(obj.id), "name": name_fn(obj), "path": path, "action": "verify"})
            return out

        orgs = items(
            Organization.objects.filter(verified=False),
            "organizations",
            lambda o: o.organization_name or "Unnamed organization",
        )
        pros = items(
            ProfessionalProfile.objects.filter(is_verified=False).select_related("user"),
            "professionals",
            lambda p: (p.user.get_full_name() if p.user else "") or (p.user.email if p.user else "Professional"),
        )
        phs = items(
            PharmacyProfile.objects.filter(is_verified=False),
            "pharmacies",
            lambda p: p.pharmacy_name or "Unnamed pharmacy",
        )
        partners = items(
            PartnerProfile.objects.filter(is_verified=False),
            "partners",
            lambda p: p.organization_name or "Unnamed partner",
        )

        groups = [
            {"key": "organizations", "label": "Organizations", "items": orgs},
            {"key": "professionals", "label": "Professionals", "items": pros},
            {"key": "pharmacies", "label": "Pharmacies", "items": phs},
            {"key": "partners", "label": "Partners", "items": partners},
        ]
        return Response({"groups": groups, "total": sum(len(g["items"]) for g in groups)})


def _breakdown(model, field):
    """Dynamic group-by count on a field — safe (no hardcoded choices)."""
    from django.db.models import Count

    try:
        rows = (
            model.objects.values(field)
            .annotate(c=Count("id"))
            .order_by("-c")
        )
        return [
            {"label": "—" if r[field] in (None, "") else str(r[field]), "value": r["c"]}
            for r in rows
        ]
    except Exception:
        return []


def _count(model):
    try:
        return model.objects.count()
    except Exception:
        return None


def _section(label, model, field=None):
    return {"label": label, "total": _count(model), "breakdown": _breakdown(model, field) if field else []}


class _MetricsView(APIView):
    permission_classes = [IsPlatformAdmin]
    title = ""

    def sections(self):
        return []

    def get(self, request):
        return Response({"title": self.title, "sections": self.sections()})


class AdminPharmacyDashboardView(_MetricsView):
    title = "Pharmacy & Commerce"

    def sections(self):
        from pharmacies.models import Order, Payment, Settlement, SettlementPayout

        return [
            _section("Orders", Order, "status"),
            _section("Payments", Payment, "status"),
            _section("Settlements", Settlement, "status"),
            _section("Payouts", SettlementPayout, "status"),
        ]


class AdminProgramsDashboardView(_MetricsView):
    title = "Community Programs"

    def sections(self):
        from communities.models import HealthProgram, Survey, IssuedCertificate, LocumJob

        return [
            _section("Health Programs", HealthProgram, "status"),
            _section("Surveys", Survey, "active"),
            _section("Certificates", IssuedCertificate, "is_emailed"),
            _section("Locum Jobs", LocumJob, "approved"),
        ]


class AdminClinicalDashboardView(_MetricsView):
    title = "Clinical Operations"

    def sections(self):
        from facilities.models import Bed, FacilityAppointment, LabTest
        from patients.models import Visitation

        return [
            _section("Beds", Bed, "status"),
            _section("Facility Appointments", FacilityAppointment, "status"),
            _section("Visitations", Visitation, "status"),
            _section("Lab Tests", LabTest, "status"),
        ]


class AdminSecurityDashboardView(_MetricsView):
    title = "Security & Compliance"

    def sections(self):
        from accounts.models import (
            SecurityEvent,
            LoginSession,
            AuthenticationAudit,
            DataAccessLog,
        )

        return [
            _section("Security Events", SecurityEvent, "severity"),
            _section("Login Sessions", LoginSession, "is_active"),
            _section("Auth Audit", AuthenticationAudit, "success"),
            _section("Data Access (PHI)", DataAccessLog, "data_type"),
        ]


dashboard_urls = [
    path("dashboard/overview/", AdminOverviewView.as_view(), name="admin_dashboard_overview"),
    path("dashboard/verifications/", AdminVerificationsView.as_view(), name="admin_dashboard_verifications"),
    path("dashboard/pharmacy/", AdminPharmacyDashboardView.as_view(), name="admin_dashboard_pharmacy"),
    path("dashboard/programs/", AdminProgramsDashboardView.as_view(), name="admin_dashboard_programs"),
    path("dashboard/clinical/", AdminClinicalDashboardView.as_view(), name="admin_dashboard_clinical"),
    path("dashboard/security/", AdminSecurityDashboardView.as_view(), name="admin_dashboard_security"),
]
