from collections import Counter

from django.db.models import Max
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from accounts.tasks import generic_send_mail
from .models import PartnerProfile, Subsidy, ProgramPartnershipRequest, ProgramMonitor
from .serializers import (
    PartnerProfileSerializer,
    SubsidySerializer,
    ProgramPartnershipRequestSerializer,
    ProgramMonitorSerializer,
    ProgramMonitorDetailSerializer,
    PartnerProgramInterventionSerializer,
    PartnerInterventionResponseSerializer,
    ProgramSummarySerializer,
    PartnerDiscoverSerializer,
)


class IsPartnerUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and hasattr(
            request.user, "partner_profile"
        )


class IsVerifiedPartner(permissions.BasePermission):
    message = "Your partner account is pending admin verification."

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and hasattr(request.user, "partner_profile")
            and request.user.partner_profile.is_verified
        )


class IsCommunityOrgMember(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            hasattr(request.user, "community_profile") or request.user.is_staff
        )


class PartnerProfileViewSet(viewsets.ModelViewSet):
    queryset = PartnerProfile.objects.all()
    serializer_class = PartnerProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        if self.action == "list":
            return [permissions.IsAdminUser()]
        return [permissions.IsAuthenticated()]

    @action(detail=False, methods=["get", "patch"])
    def me(self, request):
        try:
            profile = request.user.partner_profile
        except PartnerProfile.DoesNotExist:
            return Response(
                {"error": "Partner profile not found"}, status=status.HTTP_404_NOT_FOUND
            )

        if request.method == "PATCH":
            serializer = self.get_serializer(profile, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)

        return Response(self.get_serializer(profile).data)

    @action(detail=False, methods=["get"])
    def dashboard(self, request):
        try:
            partner = request.user.partner_profile
        except PartnerProfile.DoesNotExist:
            return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)

        subsidies = partner.subsidies.all()
        active_subsidies = subsidies.filter(status="active")
        monitors = partner.program_monitors.filter(is_active=True).select_related(
            "program"
        )
        requests_qs = partner.partnership_requests.all()

        total_budget = sum(s.total_budget for s in subsidies)
        total_used = sum(s.budget_used for s in subsidies)

        subsidy_by_type = {}
        for s in subsidies:
            subsidy_by_type[s.subsidy_type] = subsidy_by_type.get(s.subsidy_type, 0) + 1

        budget_chart = [
            {
                "name": s.name,
                "total": float(s.total_budget),
                "used": float(s.budget_used),
                "remaining": float(s.budget_remaining),
                "pct": s.utilization_pct,
                "status": s.status,
            }
            for s in subsidies
        ]

        program_outcomes = [
            {
                "id": str(m.program.id),
                "name": m.program.program_name,
                "status": m.program.status,
                "actual_participants": m.program.actual_participants,
                "target_participants": m.program.target_participants,
                "region": m.program.region,
            }
            for m in monitors
        ]

        pending_requests = requests_qs.filter(status="pending").count()
        approved_requests = requests_qs.filter(status="approved").count()
        rejected_requests = requests_qs.filter(status="rejected").count()

        return Response(
            {
                "is_verified": partner.is_verified,
                "active_subsidies": active_subsidies.count(),
                "total_subsidies": subsidies.count(),
                "total_budget": float(total_budget),
                "total_budget_used": float(total_used),
                "budget_utilization_pct": (
                    round(float(total_used) / float(total_budget) * 100, 1)
                    if total_budget
                    else 0
                ),
                "monitored_programs": monitors.count(),
                "subsidy_by_type": subsidy_by_type,
                "budget_chart": budget_chart,
                "program_outcomes": program_outcomes,
                "partnership_requests": {
                    "pending": pending_requests,
                    "approved": approved_requests,
                    "rejected": rejected_requests,
                },
            }
        )


class SubsidyViewSet(viewsets.ModelViewSet):
    serializer_class = SubsidySerializer
    permission_classes = [IsVerifiedPartner]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["subsidy_type", "status"]
    search_fields = ["name", "target"]

    def get_queryset(self):
        return Subsidy.objects.filter(partner=self.request.user.partner_profile)

    def perform_create(self, serializer):
        serializer.save(partner=self.request.user.partner_profile)


class ProgramPartnershipRequestViewSet(viewsets.ModelViewSet):
    """
    Unified endpoint for partnership requests in both directions.
    - Partners POST to create a partner_initiated request.
    - Orgs POST to /org-invite/ to create an org_initiated request.
    - unique_together on (partner, program) ensures only ONE request exists per pair.
    """

    serializer_class = ProgramPartnershipRequestSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["status", "direction"]
    http_method_names = ["get", "post", "patch", "delete"]

    def get_queryset(self):
        user = self.request.user
        if hasattr(user, "partner_profile"):
            return ProgramPartnershipRequest.objects.filter(
                partner=user.partner_profile
            ).select_related("program", "program__organization")

        if hasattr(user, "community_profile"):
            return ProgramPartnershipRequest.objects.filter(
                program__organization=user.community_profile
            ).select_related("partner", "program")

        if user.is_staff:
            return ProgramPartnershipRequest.objects.all()

        return ProgramPartnershipRequest.objects.none()

    def perform_create(self, serializer):
        """Partner initiates a request."""
        if not hasattr(self.request.user, "partner_profile"):
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied(
                "Only partner users can create partnership requests."
            )
        partner = self.request.user.partner_profile
        program = serializer.validated_data["program"]

        if ProgramPartnershipRequest.objects.filter(
            partner=partner, program=program
        ).exists():
            from rest_framework.exceptions import ValidationError

            raise ValidationError(
                {"detail": "A request already exists for this partner and program."}
            )

        instance = serializer.save(
            partner=partner,
            direction=ProgramPartnershipRequest.Direction.PARTNER_INITIATED,
        )
        self._notify_org_on_request(instance)

    def _notify_org_on_request(self, req):
        org = req.program.organization
        if not org:
            return
        org_user = getattr(org, "user", None)
        if not org_user:
            return
        try:
            from django.conf import settings
        except Exception:
            return
        generic_send_mail.delay(
            recipient=org_user.email,
            title=f"New Partnership Request for '{req.program.program_name}'",
            payload={
                "user_name": org_user.get_full_name() or org.organization_name,
                "partner_name": req.partner.organization_name,
                "partner_type": req.partner.get_organization_type_display(),
                "program_name": req.program.program_name,
                "message": req.message,
                "review_link": f"{settings.FRONTEND_URL}/community/programs",
            },
            email_type="partner_request_submitted",
        )

    @action(detail=False, methods=["post"], url_path="org-invite")
    def org_invite(self, request):
        """Community org invites a partner to monitor one of their programs."""
        if not hasattr(request.user, "community_profile"):
            return Response(
                {"error": "Only community org members can send invitations."},
                status=403,
            )

        partner_id = request.data.get("partner")
        program_id = request.data.get("program")

        if not partner_id or not program_id:
            return Response({"error": "partner and program are required."}, status=400)

        try:
            partner = PartnerProfile.objects.get(pk=partner_id)
        except PartnerProfile.DoesNotExist:
            return Response({"error": "Partner not found."}, status=404)

        # Verify the program belongs to this org
        from communities.models import HealthProgram

        try:
            program = HealthProgram.objects.get(
                pk=program_id, organization=request.user.community_profile
            )
        except HealthProgram.DoesNotExist:
            return Response(
                {"error": "Program not found or does not belong to your organisation."},
                status=404,
            )

        # Enforce uniqueness across both directions
        if ProgramPartnershipRequest.objects.filter(
            partner=partner, program=program
        ).exists():
            return Response(
                {
                    "error": "A request or invitation already exists for this partner and program."
                },
                status=status.HTTP_409_CONFLICT,
            )

        req = ProgramPartnershipRequest.objects.create(
            partner=partner,
            program=program,
            direction=ProgramPartnershipRequest.Direction.ORG_INITIATED,
            message=request.data.get("message", ""),
            report_frequency=request.data.get("report_frequency", "monthly"),
            contact=request.data.get("contact", ""),
        )

        # Notify partner
        try:
            from django.conf import settings

            generic_send_mail.delay(
                recipient=partner.organization_email or partner.user.email,
                title=f"Partnership Invitation — {program.program_name}",
                payload={
                    "user_name": partner.contact_person_name
                    or partner.organization_name,
                    "org_name": request.user.community_profile.organization_name,
                    "program_name": program.program_name,
                    "message": req.message or "No message provided.",
                    "dashboard_link": f"{settings.FRONTEND_URL}/partner/programs",
                },
                email_type="partner_request_submitted",
            )
        except Exception:
            pass

        return Response(
            ProgramPartnershipRequestSerializer(req).data,
            status=status.HTTP_201_CREATED,
        )

    def _create_monitor(self, req):
        """Create a ProgramMonitor, using get_or_create to guard against duplicates."""
        monitor, _ = ProgramMonitor.objects.get_or_create(
            partner=req.partner,
            program=req.program,
            defaults={
                "request": req,
                "report_frequency": req.report_frequency,
                "contact": req.contact or "",
            },
        )
        return monitor

    def _can_approve_reject(self, request, req):
        """
        - partner_initiated: the community org (or org staff) approves/rejects
        - org_initiated: the addressed partner approves/rejects
        """
        user = request.user
        if req.direction == ProgramPartnershipRequest.Direction.PARTNER_INITIATED:
            return self._user_owns_program_org(user, req.program)
        else:  # org_initiated
            return (
                hasattr(user, "partner_profile") and user.partner_profile == req.partner
            )

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        req = self.get_object()
        if req.status != ProgramPartnershipRequest.Status.PENDING:
            return Response(
                {"error": "Only pending requests can be approved."}, status=400
            )
        if not self._can_approve_reject(request, req):
            return Response(
                {"error": "You do not have permission to approve this request."},
                status=403,
            )

        req.status = ProgramPartnershipRequest.Status.APPROVED
        req.reviewed_by = request.user
        req.reviewed_at = timezone.now()
        req.review_note = request.data.get("review_note", "")
        req.save()

        monitor = self._create_monitor(req)

        # Notify the other party
        try:
            from django.conf import settings

            if req.direction == ProgramPartnershipRequest.Direction.PARTNER_INITIATED:
                # Notify partner
                generic_send_mail.delay(
                    recipient=req.partner.organization_email or req.partner.user.email,
                    title=f"Partnership Request Approved — {req.program.program_name}",
                    payload={
                        "user_name": req.partner.contact_person_name
                        or req.partner.organization_name,
                        "program_name": req.program.program_name,
                        "organization_name": (
                            req.program.organization.organization_name
                            if req.program.organization
                            else "the organisation"
                        ),
                        "dashboard_link": f"{settings.FRONTEND_URL}/partner/programs",
                    },
                    email_type="partner_request_approved",
                )
            else:
                # Notify org
                org_user = getattr(req.program.organization, "user", None)
                if org_user:
                    generic_send_mail.delay(
                        recipient=org_user.email,
                        title=f"Partnership Invitation Accepted — {req.program.program_name}",
                        payload={
                            "user_name": org_user.get_full_name()
                            or req.program.organization.organization_name,
                            "partner_name": req.partner.organization_name,
                            "program_name": req.program.program_name,
                            "dashboard_link": f"{settings.FRONTEND_URL}/community/programs",
                        },
                        email_type="partner_request_approved",
                    )
        except Exception:
            pass

        return Response(
            {
                "message": "Approved. Partnership monitor created.",
                "monitor_id": str(monitor.id),
            }
        )

    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        req = self.get_object()
        if req.status != ProgramPartnershipRequest.Status.PENDING:
            return Response(
                {"error": "Only pending requests can be rejected."}, status=400
            )
        if not self._can_approve_reject(request, req):
            return Response(
                {"error": "You do not have permission to reject this request."},
                status=403,
            )

        req.status = ProgramPartnershipRequest.Status.REJECTED
        req.reviewed_by = request.user
        req.reviewed_at = timezone.now()
        req.review_note = request.data.get("review_note", "")
        req.save()

        try:
            from django.conf import settings

            if req.direction == ProgramPartnershipRequest.Direction.PARTNER_INITIATED:
                generic_send_mail.delay(
                    recipient=req.partner.organization_email or req.partner.user.email,
                    title=f"Partnership Request Update — {req.program.program_name}",
                    payload={
                        "user_name": req.partner.contact_person_name
                        or req.partner.organization_name,
                        "program_name": req.program.program_name,
                        "organization_name": (
                            req.program.organization.organization_name
                            if req.program.organization
                            else "the organisation"
                        ),
                        "review_note": req.review_note or "No reason provided.",
                        "discover_link": f"{settings.FRONTEND_URL}/partner/programs",
                    },
                    email_type="partner_request_rejected",
                )
        except Exception:
            pass

        return Response({"message": "Request rejected."})

    def _user_owns_program_org(self, user, program):
        if user.is_staff:
            return True
        if (
            hasattr(user, "community_profile")
            and program.organization == user.community_profile
        ):
            return True
        try:
            from communities.models import Staff

            Staff.objects.get(
                user=user, organization=program.organization, is_active=True
            )
            return True
        except Exception:
            pass
        return False


class ProgramMonitorViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ProgramMonitorSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["is_active"]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ProgramMonitorDetailSerializer
        return super().get_serializer_class()

    def get_queryset(self):
        user = self.request.user
        if hasattr(user, "partner_profile"):
            return ProgramMonitor.objects.filter(
                partner=user.partner_profile
            ).select_related("program", "program__organization")
        if user.is_staff:
            return ProgramMonitor.objects.all()
        return ProgramMonitor.objects.none()

    def _get_program_intervention(self, monitor, intervention_id):
        return get_object_or_404(
            monitor.program.interventions.all().prefetch_related("fields"),
            pk=intervention_id,
        )

    @action(detail=True, methods=["get"])
    def interventions(self, request, pk=None):
        monitor = self.get_object()
        interventions = (
            monitor.program.interventions.all()
            .select_related("intervention_type", "program")
            .prefetch_related("fields", "intervention_responses")
            .order_by("-created_at")
        )
        serializer = PartnerProgramInterventionSerializer(interventions, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def analytics(self, request, pk=None):
        monitor = self.get_object()
        program = monitor.program
        interventions = (
            program.interventions.all()
            .select_related("intervention_type")
            .prefetch_related("intervention_responses")
        )
        responses_qs = (
            program.interventions.values("intervention_responses__id")
            .exclude(intervention_responses__id__isnull=True)
        )
        response_timestamps = (
            program.interventions.values("intervention_responses__date_created")
            .exclude(intervention_responses__date_created__isnull=True)
        )
        response_values = (
            program.interventions.values_list(
                "intervention_responses__response_values__field__name",
                "intervention_responses__response_values__value",
            )
            .exclude(intervention_responses__response_values__id__isnull=True)
        )

        interventions_by_type = Counter()
        intervention_rows = []
        for intervention in interventions:
            type_name = intervention.intervention_type.name
            interventions_by_type[type_name] += 1
            intervention_rows.append(
                {
                    "id": str(intervention.id),
                    "name": type_name,
                    "responses_count": intervention.intervention_responses.count(),
                    "fields_count": intervention.fields.count(),
                    "created_at": intervention.created_at,
                }
            )

        recent_activity = Counter()
        for item in response_timestamps:
            date_created = item.get("intervention_responses__date_created")
            if not date_created:
                continue
            recent_activity[date_created.date().isoformat()] += 1

        top_response_values = Counter()
        for field_name, value in response_values:
            if not field_name or value in (None, ""):
                continue
            values = [entry.strip() for entry in str(value).split(",") if entry.strip()]
            for entry in values:
                top_response_values[(field_name, entry)] += 1

        return Response(
            {
                "program": {
                    "id": str(program.id),
                    "name": program.program_name,
                    "status": program.status,
                    "organization_name": (
                        program.organization.organization_name
                        if program.organization
                        else None
                    ),
                    "target_participants": program.target_participants,
                    "actual_participants": program.actual_participants,
                    "participation_rate": program.participation_rate,
                    "region": program.region,
                    "district": program.district,
                    "start_date": program.start_date,
                    "end_date": program.end_date,
                },
                "summary": {
                    "total_interventions": program.interventions.count(),
                    "total_responses": responses_qs.count(),
                    "active_monitor": monitor.is_active,
                    "report_frequency": monitor.report_frequency,
                    "latest_response_at": (
                        response_timestamps.aggregate(
                            latest=Max("intervention_responses__date_created")
                        )["latest"]
                    ),
                },
                "interventions_by_type": [
                    {"name": name, "count": count}
                    for name, count in interventions_by_type.most_common()
                ],
                "recent_activity": [
                    {"date": date, "count": count}
                    for date, count in sorted(recent_activity.items())
                ],
                "top_response_values": [
                    {"field_name": field_name, "value": value, "count": count}
                    for (field_name, value), count in top_response_values.most_common(10)
                ],
                "interventions": intervention_rows,
            }
        )

    @action(
        detail=True,
        methods=["get"],
        url_path=r"interventions/(?P<intervention_id>[^/.]+)/responses",
    )
    def intervention_responses(self, request, pk=None, intervention_id=None):
        monitor = self.get_object()
        intervention = self._get_program_intervention(monitor, intervention_id)
        responses = (
            intervention.intervention_responses.all()
            .select_related("participant", "intervention", "intervention__program")
            .prefetch_related("response_values__field")
            .order_by("-date_created")
        )
        serializer = PartnerInterventionResponseSerializer(responses, many=True)
        return Response(serializer.data)


class PublicProgramViewSet(viewsets.ReadOnlyModelViewSet):
    """Lets partners discover community programs they can request to monitor."""

    permission_classes = [IsVerifiedPartner]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["status", "region", "district"]
    search_fields = ["program_name", "description", "location_name"]

    def get_queryset(self):
        from communities.models import HealthProgram

        return (
            HealthProgram.objects.filter(
                status__in=["approved", "in_progress", "planning"]
            )
            .select_related("organization", "program_type")
            .order_by("-start_date")
        )

    def get_serializer_class(self):
        return ProgramSummarySerializer

    def list(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())
        partner = request.user.partner_profile
        existing = {
            str(r.program_id): r.status
            for r in ProgramPartnershipRequest.objects.filter(partner=partner)
        }
        page = self.paginate_queryset(qs)
        data = ProgramSummarySerializer(
            page or qs, many=True, context={"request": request}
        ).data
        for item in data:
            item["request_status"] = existing.get(str(item["id"]))
        if page is not None:
            return self.get_paginated_response(data)
        return Response(data)


class DiscoverPartnersView(viewsets.ReadOnlyModelViewSet):
    """Community organisations browse verified partner profiles."""

    serializer_class = PartnerDiscoverSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["organization_type", "partnership_type", "region"]
    search_fields = ["organization_name", "contact_person_name", "region", "district"]

    def get_queryset(self):
        return PartnerProfile.objects.filter(is_verified=True).order_by(
            "organization_name"
        )

    def list(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())
        # Annotate with existing request_status for a given program
        program_id = request.query_params.get("program")
        existing = {}
        if program_id and hasattr(request.user, "community_profile"):
            existing = {
                str(r.partner_id): r.status
                for r in ProgramPartnershipRequest.objects.filter(program_id=program_id)
            }
        page = self.paginate_queryset(qs)
        data = PartnerDiscoverSerializer(
            page or qs, many=True, context={"request": request}
        ).data
        for item in data:
            item["request_status"] = existing.get(str(item["id"]))
        if page is not None:
            return self.get_paginated_response(data)
        return Response(data)
