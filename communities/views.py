from rest_framework import viewsets, status, permissions, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.db.models import Count, Q, Sum
from datetime import datetime, timedelta

from .models import (
    CommunityProfile,
    HealthProgram,
    ProgramIntervention,
    BulkInterventionUpload,
    ProgramSchedule,
    HealthSurvey,
    SurveyResponse,
    BulkSurveyUpload,
    ProgramReport,
)
from .serializers import (
    CommunityProfileSerializer,
    HealthProgramSerializer,
    ProgramInterventionSerializer,
    BulkInterventionUploadSerializer,
    ProgramScheduleSerializer,
    HealthSurveySerializer,
    SurveyResponseSerializer,
    BulkSurveyUploadSerializer,
    ProgramReportSerializer,
    ProgramStatisticsSerializer,
)


class CommunityProfileViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing community profiles
    """
    queryset = CommunityProfile.objects.all()
    serializer_class = CommunityProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['organization_type', 'volunteer_status', 'coordinator_level']
    search_fields = ['user__email', 'organization_name', 'organization_type']

    def get_permissions(self):
        if self.action in ['list']:
            permission_classes = [permissions.IsAdminUser]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]

    @action(detail=False, methods=['get'])
    def me(self, request):
        """Get current user's community profile"""
        try:
            profile = request.user.community_profile
            serializer = self.get_serializer(profile)
            return Response(serializer.data)
        except CommunityProfile.DoesNotExist:
            return Response(
                {'error': 'Community profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=False, methods=['patch'])
    def update_my_profile(self, request):
        """Update current user's community profile"""
        try:
            profile = request.user.community_profile
            serializer = self.get_serializer(profile, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except CommunityProfile.DoesNotExist:
            return Response(
                {'error': 'Community profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class HealthProgramViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing health programs
    """

    queryset = HealthProgram.objects.all()
    serializer_class = HealthProgramSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
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
        "lead_organizer",
        "organization__organization_name",
    ]
    ordering_fields = ["start_date", "created_at", "actual_participants"]
    ordering = ["-start_date"]

    def perform_create(self, serializer):
        """Set created_by and organization to current user's community profile"""
        user = self.request.user
        
        # Check if user has a community profile
        if not hasattr(user, 'community_profile'):
            from rest_framework.exceptions import ValidationError
            raise ValidationError({
                'organization': 'User must have a community profile to create programs. '
                               'Please ensure the user is registered as a community organization.'
            })
        
        serializer.save(
            created_by=user,
            organization=user.community_profile
        )

    @action(detail=False, methods=["get"])
    def my_programs(self, request):
        """Get programs created by or involving current user"""
        queryset = self.get_queryset().filter(
            Q(created_by=request.user) | Q(team_members=request.user)
        ).distinct()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def active(self, request):
        """Get currently active programs"""
        today = timezone.now().date()
        queryset = self.get_queryset().filter(
            status="in_progress", start_date__lte=today
        )
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def upcoming(self, request):
        """Get upcoming programs"""
        today = timezone.now().date()
        queryset = self.get_queryset().filter(
            status__in=["planning", "approved"], start_date__gt=today
        )
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def start_program(self, request, pk=None):
        """Mark program as in progress"""
        program = self.get_object()
        if program.status != "approved":
            return Response(
                {"error": "Only approved programs can be started"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        program.status = "in_progress"
        program.save()
        return Response({"message": "Program started successfully"})

    @action(detail=True, methods=["post"])
    def complete_program(self, request, pk=None):
        """Mark program as completed"""
        program = self.get_object()
        program.status = "completed"
        program.save()
        return Response({"message": "Program marked as completed"})

    @action(detail=True, methods=["get"])
    def statistics(self, request, pk=None):
        """Get statistics for a specific program"""
        program = self.get_object()
        stats = {
            "total_interventions": program.interventions.count(),
            "participants_reached": program.actual_participants,
            "participation_rate": program.participation_rate,
            "interventions_by_type": dict(
                program.interventions.values("intervention_type").annotate(
                    count=Count("id")
                ).values_list("intervention_type", "count")
            ),
            "referrals_made": program.interventions.filter(referral_needed=True).count(),
            "surveys_conducted": program.surveys.count(),
        }
        return Response(stats)


class ProgramInterventionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing program interventions
    """

    queryset = ProgramIntervention.objects.all()
    serializer_class = ProgramInterventionSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = [
        "program",
        "intervention_type",
        "participant_gender",
        "referral_needed",
        "synced_to_ehr",
    ]
    search_fields = [
        "participant_name",
        "participant_id",
        "intervention_name",
        "diagnosis",
    ]
    ordering_fields = ["documented_at"]
    ordering = ["-documented_at"]

    def perform_create(self, serializer):
        """Set documented_by to current user"""
        serializer.save(documented_by=self.request.user)

    @action(detail=False, methods=["get"])
    def by_program(self, request):
        """Get interventions for a specific program"""
        program_id = request.query_params.get("program_id")
        if not program_id:
            return Response(
                {"error": "program_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        queryset = self.get_queryset().filter(program_id=program_id)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def referrals(self, request):
        """Get all interventions requiring referral"""
        queryset = self.get_queryset().filter(referral_needed=True)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def unsynced(self, request):
        """Get interventions not yet synced to EHR"""
        queryset = self.get_queryset().filter(synced_to_ehr=False)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class BulkInterventionUploadViewSet(viewsets.ModelViewSet):
    """
    ViewSet for bulk intervention uploads
    """

    queryset = BulkInterventionUpload.objects.all()
    serializer_class = BulkInterventionUploadSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["program", "status"]
    ordering_fields = ["uploaded_at"]
    ordering = ["-uploaded_at"]

    def perform_create(self, serializer):
        """Set uploaded_by to current user"""
        serializer.save(uploaded_by=self.request.user)


class ProgramScheduleViewSet(viewsets.ModelViewSet):
    """
    ViewSet for program schedules
    """

    queryset = ProgramSchedule.objects.all()
    serializer_class = ProgramScheduleSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["program", "is_confirmed", "transportation_arranged"]
    ordering_fields = ["scheduled_date", "start_time"]
    ordering = ["scheduled_date", "start_time"]

    def perform_create(self, serializer):
        """Set created_by to current user"""
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=["get"])
    def upcoming(self, request):
        """Get upcoming schedules"""
        today = timezone.now().date()
        queryset = self.get_queryset().filter(scheduled_date__gte=today)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        """Confirm a schedule"""
        schedule = self.get_object()
        schedule.is_confirmed = True
        schedule.save()
        return Response({"message": "Schedule confirmed"})


class HealthSurveyViewSet(viewsets.ModelViewSet):
    """
    ViewSet for health surveys
    """

    queryset = HealthSurvey.objects.all()
    serializer_class = HealthSurveySerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["survey_type", "status", "program"]
    search_fields = ["title", "description", "target_audience"]
    ordering_fields = ["start_date", "created_at", "actual_responses"]
    ordering = ["-created_at"]

    def get_permissions(self):
        """Allow public access to active surveys if not requiring authentication"""
        if self.action in ["retrieve", "list"] and self.request.method == "GET":
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        """Set created_by to current user"""
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=["get"], permission_classes=[permissions.AllowAny])
    def active(self, request):
        """Get active surveys"""
        today = timezone.now().date()
        queryset = self.get_queryset().filter(
            status="active",
            start_date__lte=today,
        )
        # Filter out end_date if it exists and is in the past
        queryset = queryset.filter(
            Q(end_date__gte=today) | Q(end_date__isnull=True)
        )
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        """Activate a survey"""
        survey = self.get_object()
        if survey.status != "draft":
            return Response(
                {"error": "Only draft surveys can be activated"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        survey.status = "active"
        survey.save()
        return Response({"message": "Survey activated"})

    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        """Close a survey"""
        survey = self.get_object()
        survey.status = "closed"
        survey.save()
        return Response({"message": "Survey closed"})

    @action(detail=True, methods=["get"])
    def analytics(self, request, pk=None):
        """Get survey analytics"""
        survey = self.get_object()
        # Basic analytics - can be expanded
        analytics = {
            "total_responses": survey.responses.count(),
            "target_count": survey.target_count,
            "response_rate": survey.response_rate,
            "responses_by_gender": dict(
                survey.responses.values("respondent_gender").annotate(
                    count=Count("id")
                ).values_list("respondent_gender", "count")
            ),
            "responses_by_location": dict(
                survey.responses.values("respondent_location").annotate(
                    count=Count("id")
                ).values_list("respondent_location", "count")
            ),
        }
        return Response(analytics)


class SurveyResponseViewSet(viewsets.ModelViewSet):
    """
    ViewSet for survey responses
    """

    queryset = SurveyResponse.objects.all()
    serializer_class = SurveyResponseSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["survey", "respondent_gender", "respondent_location"]
    ordering_fields = ["submitted_at"]
    ordering = ["-submitted_at"]

    def get_permissions(self):
        """Allow public submission if survey doesn't require authentication"""
        if self.action == "create":
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        """Set respondent if authenticated"""
        if self.request.user.is_authenticated:
            serializer.save(respondent=self.request.user)
        else:
            serializer.save()

    @action(detail=False, methods=["get"], permission_classes=[permissions.IsAuthenticated])
    def my_responses(self, request):
        """Get responses by current user"""
        queryset = self.get_queryset().filter(respondent=request.user)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class BulkSurveyUploadViewSet(viewsets.ModelViewSet):
    """
    ViewSet for bulk survey uploads
    """

    queryset = BulkSurveyUpload.objects.all()
    serializer_class = BulkSurveyUploadSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["survey", "status"]
    ordering_fields = ["uploaded_at"]
    ordering = ["-uploaded_at"]

    def perform_create(self, serializer):
        """Set uploaded_by to current user"""
        serializer.save(uploaded_by=self.request.user)


class ProgramReportViewSet(viewsets.ModelViewSet):
    """
    ViewSet for program reports
    """

    queryset = ProgramReport.objects.all()
    serializer_class = ProgramReportSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["program", "report_type"]
    search_fields = ["title", "description"]
    ordering_fields = ["generated_at"]
    ordering = ["-generated_at"]

    def perform_create(self, serializer):
        """Set generated_by to current user"""
        serializer.save(generated_by=self.request.user)

    @action(detail=False, methods=["get"])
    def by_program(self, request):
        """Get reports for a specific program"""
        program_id = request.query_params.get("program_id")
        if not program_id:
            return Response(
                {"error": "program_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        queryset = self.get_queryset().filter(program_id=program_id)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


# Analytics and Statistics Views
class CommunityAnalyticsViewSet(viewsets.ViewSet):
    """
    ViewSet for community-wide analytics
    """

    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=["get"])
    def overview(self, request):
        """Get overall statistics"""
        today = timezone.now().date()

        stats = {
            "total_programs": HealthProgram.objects.count(),
            "active_programs": HealthProgram.objects.filter(
                status="in_progress"
            ).count(),
            "completed_programs": HealthProgram.objects.filter(
                status="completed"
            ).count(),
            "total_participants": HealthProgram.objects.aggregate(
                total=Sum("actual_participants")
            )["total"]
            or 0,
            "total_interventions": ProgramIntervention.objects.count(),
            "total_surveys": HealthSurvey.objects.count(),
            "programs_by_type": dict(
                HealthProgram.objects.values("program_type").annotate(
                    count=Count("id")
                ).values_list("program_type", "count")
            ),
            "programs_by_region": dict(
                HealthProgram.objects.values("region").annotate(
                    count=Count("id")
                ).values_list("region", "count")
            ),
        }

        serializer = ProgramStatisticsSerializer(stats)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def monthly_trends(self, request):
        """Get monthly program trends"""
        # Last 12 months
        today = timezone.now().date()
        twelve_months_ago = today - timedelta(days=365)

        programs = HealthProgram.objects.filter(
            start_date__gte=twelve_months_ago
        ).values("start_date__year", "start_date__month").annotate(
            count=Count("id")
        ).order_by("start_date__year", "start_date__month")

        return Response(list(programs))
