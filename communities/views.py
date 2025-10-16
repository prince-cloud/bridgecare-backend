from rest_framework import viewsets, status, permissions, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.db.models import Count, Q, Sum
from datetime import datetime, timedelta
from django_filters import rest_framework as djangofilters
from django_filters.rest_framework import DjangoFilterBackend
from .models import (
    Organization,
    HealthProgram,
    ProgramIntervention,
    BulkInterventionUpload,
    Survey,
    SurveyType,
    SurveyQuestionOption,
    SurveyQuestion,
    SurveyResponse,
    SurveyResponse,
    SurveyResponseAnswers,
    BulkSurveyUpload,
)
from .serializers import (
    OrganizationCreateSerializer,
    OrganizationSerializer,
    HealthProgramSerializer,
    ProgramInterventionSerializer,
    BulkInterventionUploadSerializer,
    SurveySerializer,
    SurveyResponseSerializer,
    BulkSurveyUploadSerializer,
    ProgramStatisticsSerializer,
    SurveyQuesitonOptionSerializer,
    SurveyQuestionSerializer,
    SurveySerializer,
    SurveyDetailSerializer,
    SurveyCreateOptionSerializer,
    SurveyCreateQuestionSerializer,
    SurveyCreateSerializer,
    SurveyAnswersSerializer,
    SurveyAnswerCreateSerializer,
    SurveyQuestionSerializer,
    SurveyResponseAnswerSerializer,
)
from rest_framework.views import APIView
from django.db import transaction


class OrganizationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing organizations
    """

    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["organization_type"]
    search_fields = ["user__email", "organization_name", "organization_type"]

    def get_serializer_class(self):
        if self.action == "list":
            return OrganizationSerializer
        return OrganizationCreateSerializer

    def get_permissions(self):
        if self.action in ["list"]:
            permission_classes = [permissions.IsAdminUser]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]

    @action(detail=False, methods=["get"])
    def me(self, request):
        """Get current user's organization profile"""
        try:
            profile = request.user.community_profile
            serializer = self.get_serializer(profile)
            return Response(serializer.data)
        except Organization.DoesNotExist:
            return Response(
                {"error": "Organization profile not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

    @action(detail=False, methods=["patch"])
    def update_my_profile(self, request):
        """Update current user's organization profile"""
        try:
            profile = request.user.community_profile
            serializer = self.get_serializer(profile, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Organization.DoesNotExist:
            return Response(
                {"error": "Organization profile not found"},
                status=status.HTTP_404_NOT_FOUND,
            )


class HealthProgramViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing health programs
    """

    queryset = HealthProgram.objects.all()
    serializer_class = HealthProgramSerializer
    permission_classes = [permissions.IsAuthenticated]
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
        "lead_organizer",
        "organization__organization_name",
    ]
    ordering_fields = ["start_date", "created_at", "actual_participants"]
    ordering = ["-start_date"]

    def perform_create(self, serializer):
        """Set created_by and organization to current user's community profile"""
        user = self.request.user

        # Check if user has an organization profile
        if not hasattr(user, "community_profile"):
            from rest_framework.exceptions import ValidationError

            raise ValidationError(
                {
                    "organization": "User must have an organization profile to create programs. "
                    "Please ensure the user is registered as a community organization."
                }
            )

        serializer.save(created_by=user, organization=user.community_profile)

    @action(detail=False, methods=["get"])
    def my_programs(self, request):
        """Get programs created by or involving current user"""
        queryset = (
            self.get_queryset()
            .filter(Q(created_by=request.user) | Q(team_members=request.user))
            .distinct()
        )
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
                program.interventions.values("intervention_type")
                .annotate(count=Count("id"))
                .values_list("intervention_type", "count")
            ),
            "referrals_made": program.interventions.filter(
                referral_needed=True
            ).count(),
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
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
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


class SurveyFilter(djangofilters.FilterSet):
    date_created_start_date = djangofilters.DateFilter(
        field_name="date_created", lookup_expr="gte", required=False
    )
    date_created_end_date = djangofilters.DateFilter(
        field_name="date_created", lookup_expr="lte", required=False
    )

    class Meta:
        model = Survey
        fields = (
            "end_date",
            "active",
        )

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)

        date_created_start_date = self.data.get("date_created_start_date")
        date_created_end_date = self.data.get("date_created_end_date")

        if date_created_start_date and date_created_end_date:
            queryset = queryset.filter(
                date_created__gte=date_created_start_date,
                date_created__lte=date_created_end_date,
            )
        elif date_created_start_date:
            queryset = queryset.filter(date_created__gte=date_created_start_date)
        elif date_created_end_date:
            queryset = queryset.filter(date_created__lte=date_created_end_date)

        return queryset


class SurveyViewset(viewsets.ModelViewSet):
    queryset = Survey.objects.all()
    serializer_class = SurveySerializer
    http_method_names = ["get", "post"]
    filter_backends = (filters.SearchFilter, DjangoFilterBackend)
    filterset_class = SurveyFilter
    search_fields = ["title", "description"]

    def get_serializer_class(self):  # type: ignore[override]
        if self.request.method == "POST":
            return SurveyCreateSerializer
        if self.action == "retrieve":
            return SurveyDetailSerializer
        return super().get_serializer_class()

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()

        if not instance.active:
            # if the end date is passed
            if instance.end_date < timezone.now():
                instance.active = False
                instance.save()

        return super().retrieve(request, *args, **kwargs)


class SurveyCreateView(APIView):
    serializer_class = SurveyCreateSerializer

    @transaction.atomic
    def post(self, request):
        serializer = SurveyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        questions = data["questions"]

        # create survye
        survey = Survey.objects.create(
            created_by=request.user,
            title=data["title"],
            description=data["description"],
            end_date=data["end_date"],
        )

        # create survey questions and options
        for qtn in questions:
            question = SurveyQuestion.objects.create(
                survey=survey,
                question_type=qtn["question_type"],
                question=qtn["question"],
                required=qtn["required"],
            )

            if "options" in qtn:
                for option in qtn["options"]:
                    SurveyQuestionOption.objects.create(
                        question=question,
                        **option,
                    )

        return Response(serializer.data, status=status.HTTP_201_CREATED)


class SurveyAnswerView(APIView):
    serializer_class = SurveyAnswerCreateSerializer

    @transaction.atomic
    def post(self, request):
        serializer = SurveyAnswerCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        # get survey object
        survey = Survey.objects.get(id=data["survey"])
        # create survey  response
        response = SurveyResponse.objects.create(
            survey=survey,
            phone_number=data["phone_number"],
        )

        # create survey anssers
        for answer in data["answers"]:
            question = SurveyQuestion.objects.get(id=answer["question"])
            SurveyResponseAnswers.objects.create(
                response=response,
                question=question,
                answer=answer["answer"],
            )
        return Response(
            data=SurveyResponseSerializer(response).data,
            status=status.HTTP_201_CREATED,
        )


class SurveyResponseViewset(viewsets.ModelViewSet):
    queryset = SurveyResponse.objects.all()
    serializer_class = SurveyResponseSerializer
    http_method_names = ["get"]
    filterset_fields = ["survey"]
    search_fields = ["title", "description"]

    def get_queryset(self):
        # get query param
        survey_id = self.request.query_params.get("survey")
        return super().get_queryset().filter(survey=survey_id)


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
            "total_surveys": Survey.objects.count(),
            "programs_by_type": dict(
                HealthProgram.objects.values("program_type")
                .annotate(count=Count("id"))
                .values_list("program_type", "count")
            ),
            "programs_by_region": dict(
                HealthProgram.objects.values("region")
                .annotate(count=Count("id"))
                .values_list("region", "count")
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

        programs = (
            HealthProgram.objects.filter(start_date__gte=twelve_months_ago)
            .values("start_date__year", "start_date__month")
            .annotate(count=Count("id"))
            .order_by("start_date__year", "start_date__month")
        )

        return Response(list(programs))
