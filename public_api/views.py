from django.db.models import Q, Min, Sum, Max
from communities import models as community_models
from rest_framework.viewsets import ModelViewSet
from django.utils import timezone
from professionals.models import ProfessionalProfile
from . import serializers
from rest_framework import filters
from django_filters.rest_framework import DjangoFilterBackend
from django_filters import rest_framework as django_filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from pharmacies import models as pharmacy_models
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.exceptions import ValidationError as DRFValidationError
from django.conf import settings
from loguru import logger
from accounts.tasks import send_mail_now
from helpers.captcha import (
    attempt_count,
    captcha_enabled,
    challenge_required,
    challenge_threshold,
    record_attempt,
    reset_attempts,
    verify_captcha,
)
from .models import ContactEnquiry


def _enquiry_client_ip(request):
    """Best-effort client IP behind a proxy."""
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR") or None


""" LOCUM JOBS """


class LocumJobFilter(django_filters.FilterSet):
    """
    Custom filter set for LocumJob that supports multiple role and renumeration_frequency filtering
    """

    role = django_filters.ModelMultipleChoiceFilter(
        queryset=community_models.LocumJobRole.objects.all(),
        field_name="role",
    )
    renumeration_frequency = django_filters.MultipleChoiceFilter(
        choices=[
            ("hourly", "Hourly"),
            ("daily", "Daily"),
            ("weekly", "Weekly"),
            ("monthly", "Monthly"),
            ("yearly", "Yearly"),
        ],
        field_name="renumeration_frequency",
    )

    class Meta:
        model = community_models.LocumJob
        fields = [
            "role",
            "organization",
            "is_active",
            "approved",
            "renumeration_frequency",
        ]


class LocumJobsViewset(ModelViewSet):
    queryset = community_models.LocumJob.objects.filter(approved=True, is_active=True)
    serializer_class = serializers.LocumJobSerializer
    http_method_names = ["get"]
    lookup_field = "slug"

    def get_queryset(self):
        """
        Public listing shows only approved, active jobs that have NOT expired.
        A job expires once the latest program it is attached to has ended;
        such jobs stay visible on the organizer's portal (and to applicants),
        but disappear from the public profile.
        """
        today = timezone.now().date()
        return (
            super()
            .get_queryset()
            .annotate(_latest_program_end=Max("locum_needs__program__end_date"))
            .filter(
                Q(_latest_program_end__isnull=True)
                | Q(_latest_program_end__gte=today)
            )
        )
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_class = LocumJobFilter
    search_fields = [
        "title",
        "description",
        "location",
        "organization__organization_name",
    ]
    ordering_fields = ["date_created", "renumeration", "title"]
    ordering = ["-date_created"]

    @action(
        detail=False,
        methods=["get"],
        url_path="roles",
        url_name="roles",
    )
    def get_roles(self, request):
        """Get recent locum jobs"""
        recent_jobs = community_models.LocumJobRole.objects.all()
        return Response(
            data=serializers.LocumJobRoleSerializer(
                recent_jobs,
                many=True,
                context={"request": request},
            ).data,
            status=status.HTTP_200_OK,
        )


""" HEATH PROFESSIONALS """


class ProfessionalProfileViewSet(ModelViewSet):
    """
    ViewSet for managing professional profiles
    """

    queryset = ProfessionalProfile.objects.filter(
        Q(availability__patient_visit_availability=True)
        | Q(availability__provider_visit_availability=True)
        | Q(availability__telehealth_availability=True),
        is_verified=True,
    )
    serializer_class = serializers.ProfessionalProfileSerializer
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = [
        "profession",
        "specialization",
        "education_status",
        "facility_affiliation",
        "is_verified",
    ]
    # `SearchFilter` does nothing without this list, so `?search=` was
    # ignored and every query returned the full list (QA finding MSG-02).
    search_fields = [
        "user__first_name",
        "user__last_name",
        "profession__name",
        "specialization__name",
    ]
    http_method_names = ["get"]


""" PHARMACIES """


class InventoryViewSet(ModelViewSet):
    """
    Public pharmacy inventory. Supports location-based sorting via ?lat=&lng= query params.
    """

    serializer_class = serializers.DrugInventorySerializer
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    search_fields = ["name", "category__name", "base_unit"]
    ordering_fields = [
        "name",
        "available_quantity",
        "nearest_expiry",
        "unit_price",
        "created_at",
    ]
    ordering = ["name"]
    http_method_names = ["get"]

    def get_queryset(self):
        today = timezone.now().date()
        return (
            pharmacy_models.Drug.objects.filter(pharmacy__is_verified=True)
            .annotate(
                available_quantity=Sum(
                    "movements__quantity",
                    filter=Q(movements__batch__expiry_date__gte=today),
                ),
                nearest_expiry=Min(
                    "batches__expiry_date",
                    filter=Q(batches__expiry_date__gte=today),
                ),
            )
            .filter(available_quantity__gt=0)
            .select_related("category", "pharmacy")
        )

    def list(self, request, *args, **kwargs):
        from .serializers import haversine_km

        lat_param = request.query_params.get("lat")
        lng_param = request.query_params.get("lng")

        queryset = self.filter_queryset(self.get_queryset())

        # Location-aware path: sort by distance
        if lat_param and lng_param:
            try:
                user_lat = float(lat_param)
                user_lng = float(lng_param)
            except (ValueError, TypeError):
                user_lat = user_lng = None
        else:
            user_lat = user_lng = None

        if user_lat is not None:
            drugs = list(queryset)
            distances = {}
            for drug in drugs:
                p = drug.pharmacy
                if p.latitude and p.longitude:
                    distances[drug.id] = haversine_km(
                        user_lat, user_lng, float(p.latitude), float(p.longitude)
                    )
                else:
                    distances[drug.id] = float("inf")

            drugs.sort(key=lambda d: distances[d.id])

            page = self.paginate_queryset(drugs)
            ctx = {**self.get_serializer_context(), "distances": distances}
            if page is not None:
                serializer = self.get_serializer(page, many=True, context=ctx)
                return self.get_paginated_response(serializer.data)
            serializer = self.get_serializer(drugs, many=True, context=ctx)
            return Response(serializer.data)

        # Default path (no location)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class HealthProgramViewSet(ModelViewSet):
    """
    ViewSet for managing health programs
    """

    queryset = community_models.HealthProgram.objects.filter(
        status__in=["approved", "in_progress"]
    )
    serializer_class = serializers.HealthProgramSerializer
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = [
        "program_type",
        "status",
        "district",
        "region",
        "organization",
        "created_by",
    ]
    search_fields = [
        "program_name",
        "description",
        "location_name",
        "organization__organization_name",
    ]
    ordering_fields = ["start_date", "created_at", "actual_participants"]
    ordering = ["-start_date"]
    http_method_names = ["get"]


""" CONTACT / ENQUIRIES """


class ContactEnquiryView(APIView):
    """
    Public "Let's Talk" contact form.

    The audit found submissions were silently lost: the form never reached a
    backend at all. This endpoint persists every enquiry first, then attempts
    the internal notification, and reports the real outcome so the visitor is
    never told a message went through when it did not.
    """

    permission_classes = [AllowAny]
    serializer_class = serializers.ContactEnquirySerializer
    throttle_scope = "contact_form"

    # Counted per client. The challenge stays hidden for the first few
    # submissions: this form is how prospective patients and partners reach the
    # business (audit finding 3.4), so putting a puzzle in front of every
    # first-time visitor would cost exactly the leads the fix was meant to save.
    CHALLENGE_SCOPE = "contact_form"

    def get(self, request):
        """Whether this client must solve a challenge before submitting."""
        client = _enquiry_client_ip(request) or "0.0.0.0"
        return Response(
            {
                "captcha_required": challenge_required(self.CHALLENGE_SCOPE, client),
                "captcha_enabled": captcha_enabled(),
                "attempts": attempt_count(self.CHALLENGE_SCOPE, client),
                "challenge_after": challenge_threshold(),
            },
            status=status.HTTP_200_OK,
        )

    def get_throttles(self):
        # The status GET is polled on page load and only reads a counter.
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return []
        return super().get_throttles()

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        honeypot = (data.pop("website", "") or "").strip()
        captcha_token = (data.pop("captcha_token", "") or "").strip()

        client = _enquiry_client_ip(request) or "0.0.0.0"
        must_solve = challenge_required(self.CHALLENGE_SCOPE, client)
        solved = (
            bool(captcha_token) and verify_captcha(captcha_token, client)
            if captcha_enabled()
            else False
        )

        if must_solve and not solved:
            # Not counted as an attempt — the enquiry has not been accepted
            # yet, and counting it would make the challenge impossible to clear.
            return Response(
                {
                    "status": "error",
                    "captcha_required": True,
                    "message": (
                        "Please confirm you're not a robot to send your message."
                        if not captcha_token
                        else "That verification did not pass. Please try again."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if solved:
            reset_attempts(self.CHALLENGE_SCOPE, client)
        else:
            record_attempt(self.CHALLENGE_SCOPE, client)

        enquiry = ContactEnquiry.objects.create(
            **data,
            # A filled honeypot means a bot; keep the record but flag it so it
            # does not sit in the team's queue.
            status="spam" if honeypot else "new",
            ip_address=_enquiry_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:1000],
        )

        if honeypot:
            logger.info(f"Contact form honeypot triggered from {enquiry.ip_address}")
            # Respond as success so a bot learns nothing from the difference.
            return Response(
                {
                    "status": "success",
                    "captcha_required": challenge_required(
                        self.CHALLENGE_SCOPE, client
                    ),
                    "message": "Thanks — we've received your message.",
                },
                status=status.HTTP_201_CREATED,
            )

        recipient = getattr(settings, "CONTACT_FORM_RECIPIENT", "") or getattr(
            settings, "DEFAULT_FROM_EMAIL", ""
        )
        delivered = False
        if recipient:
            delivered = send_mail_now(
                recipient=recipient,
                title=f"New enquiry from {enquiry.full_name}",
                payload={
                    "user_name": enquiry.full_name,
                    "company_name": enquiry.company_name,
                    "sender_email": enquiry.email,
                    "phone_number": enquiry.phone_number,
                    "enquiry_message": enquiry.message,
                },
                email_type="contact_enquiry",
            )
        else:
            logger.error(
                "CONTACT_FORM_RECIPIENT and DEFAULT_FROM_EMAIL are both unset; "
                f"enquiry {enquiry.id} stored but nobody was notified"
            )

        if delivered != enquiry.notification_sent:
            enquiry.notification_sent = delivered
            enquiry.save(update_fields=["notification_sent", "updated_at"])

        # The enquiry is safely stored either way, so this is always a success
        # for the visitor; the notification failure is the team's problem and
        # is visible in the admin and the logs.
        return Response(
            {
                "status": "success",
                # Lets the form show the challenge up front on the next attempt.
                "captcha_required": challenge_required(self.CHALLENGE_SCOPE, client),
                "message": (
                    "Thanks — we've received your message and will be in touch "
                    "within 24 hours."
                ),
                "reference": str(enquiry.id),
            },
            status=status.HTTP_201_CREATED,
        )
