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
    OrganizationFiles,
    HealthProgramType,
    HealthProgram,
    ProgramInterventionType,
    ProgramIntervention,
    InterventionField,
    InterventionFieldOption,
    InterventionResponse,
    InterventionResponseValue,
    BulkInterventionUpload,
    Survey,
    SurveyType,
    SurveyQuestionOption,
    SurveyQuestion,
    SurveyResponse,
    SurveyResponseAnswers,
    BulkSurveyUpload,
)
from .serializers import (
    OrganizationCreateSerializer,
    OrganizationSerializer,
    HealthProgramTypeSerializer,
    HealthProgramSerializer,
    ProgramInterventionTypeSerializer,
    ProgramInterventionSerializer,
    ProgramInterventionDetailSerializer,
    InterventionCreateSerializer,
    InterventionResponseSerializer,
    InterventionResponseCreateSerializer,
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
        elif self.action == "create":
            return OrganizationCreateSerializer
        return OrganizationSerializer

    def get_permissions(self):
        if self.action in ["list"]:
            permission_classes = [permissions.IsAdminUser]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]

    @transaction.atomic
    def perform_create(self, serializer):
        """Create organization and handle file attachments"""
        # Get the validated data
        data = serializer.validated_data.copy()

        # Extract documentation files
        documentation_files = data.pop("documentation", [])

        # Create the organization
        organization = Organization.objects.create(user=self.request.user, **data)

        # Handle file attachments using the new serializer structure
        for file_data in documentation_files:
            if file_data and file_data.get("file"):
                # Extract file information from OrganizationCreateFilesSerializer
                uploaded_file = file_data["file"]
                document_type = file_data["document_type"]
                file_name = uploaded_file.name
                file_type = uploaded_file.content_type

                # Create OrganizationFiles record
                OrganizationFiles.objects.create(
                    organization=organization,
                    file=uploaded_file,
                    file_name=file_name,
                    file_type=file_type,
                    document_type=document_type,
                )

        return organization

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
        """Get programs created by current user"""
        queryset = self.get_queryset().filter(created_by=request.user)
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


class HealthProgramTypeViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing health program types
    """

    queryset = HealthProgramType.objects.all()
    serializer_class = HealthProgramTypeSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["default"]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]

    def get_permissions(self):
        """Allow read access to all authenticated users, write access to admin users"""
        if self.action in ["list", "retrieve"]:
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [permissions.IsAdminUser]
        return [permission() for permission in permission_classes]

    @action(detail=False, methods=["get"])
    def default_types(self, request):
        """Get default health program types"""
        queryset = self.get_queryset().filter(default=True)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def assign_to_organization(self, request, pk=None):
        """Assign this program type to an organization"""
        program_type = self.get_object()
        organization_id = request.data.get("organization_id")

        if not organization_id:
            return Response(
                {"error": "organization_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            organization = Organization.objects.get(id=organization_id)
            program_type.organizations.add(organization)
            return Response(
                {
                    "message": f"Program type '{program_type.name}' assigned to organization '{organization.organization_name}'"
                }
            )
        except Organization.DoesNotExist:
            return Response(
                {"error": "Organization not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

    @action(detail=True, methods=["post"])
    def remove_from_organization(self, request, pk=None):
        """Remove this program type from an organization"""
        program_type = self.get_object()
        organization_id = request.data.get("organization_id")

        if not organization_id:
            return Response(
                {"error": "organization_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            organization = Organization.objects.get(id=organization_id)
            program_type.organizations.remove(organization)
            return Response(
                {
                    "message": f"Program type '{program_type.name}' removed from organization '{organization.organization_name}'"
                }
            )
        except Organization.DoesNotExist:
            return Response(
                {"error": "Organization not found"},
                status=status.HTTP_404_NOT_FOUND,
            )


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


# Program Intervention API Views (similar to Survey API)
class InterventionCreateView(APIView):
    """
    APIView for creating program interventions with fields (similar to SurveyCreateView)
    """

    serializer_class = InterventionCreateSerializer
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        """Create intervention with fields and options"""
        serializer = InterventionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        fields_data = data["fields"]

        # Create the intervention
        intervention = ProgramIntervention.objects.create(
            intervention_type=data["intervention_type"], program=data["program"]
        )

        # Create fields and options
        for field_data in fields_data:
            options_data = field_data.pop("options", [])

            field = InterventionField.objects.create(
                intervention=intervention, **field_data
            )

            # Create options for this field
            for option_data in options_data:
                InterventionFieldOption.objects.create(field=field, **option_data)

        return Response(
            {
                "message": "Intervention created successfully",
                "intervention_id": intervention.id,
                "fields_created": len(fields_data),
            },
            status=status.HTTP_201_CREATED,
        )


class InterventionAnswerView(APIView):
    """
    APIView for submitting intervention responses (similar to SurveyAnswerView)
    """

    serializer_class = InterventionResponseCreateSerializer
    permission_classes = [permissions.AllowAny]  # Allow anonymous responses

    @transaction.atomic
    def post(self, request):
        """Submit intervention response with answers"""
        serializer = InterventionResponseCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        answers_data = data["answers"]

        # Get intervention object
        intervention = data["intervention"]

        # Create intervention response
        response = InterventionResponse.objects.create(
            intervention=intervention,
            participant_id=data.get("participant_id"),
            patient_record=data.get("patient_record"),
        )

        # Create response values for each answer
        for answer_data in answers_data:
            InterventionResponseValue.objects.create(
                participant=response,
                field_id=answer_data["field"],
                value=answer_data["value"],
            )

        return Response(
            {
                "message": "Intervention response submitted successfully",
                "response_id": response.id,
                "answers_submitted": len(answers_data),
            },
            status=status.HTTP_201_CREATED,
        )


# Program Intervention Views
class ProgramInterventionTypeViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing program intervention types
    """

    queryset = ProgramInterventionType.objects.all()
    serializer_class = ProgramInterventionTypeSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["default"]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]

    def get_permissions(self):
        """Allow read access to all authenticated users, write access to admin users"""
        if self.action in ["list", "retrieve"]:
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [permissions.IsAdminUser]
        return [permission() for permission in permission_classes]

    @action(detail=False, methods=["get"])
    def default_types(self, request):
        """Get default program intervention types"""
        queryset = self.get_queryset().filter(default=True)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def assign_to_organization(self, request, pk=None):
        """Assign this intervention type to an organization"""
        intervention_type = self.get_object()
        organization_id = request.data.get("organization_id")

        if not organization_id:
            return Response(
                {"error": "organization_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            organization = Organization.objects.get(id=organization_id)
            intervention_type.organizations.add(organization)
            return Response(
                {
                    "message": f"Intervention type '{intervention_type.name}' assigned to organization '{organization.organization_name}'"
                }
            )
        except Organization.DoesNotExist:
            return Response(
                {"error": "Organization not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

    @action(detail=True, methods=["post"])
    def remove_from_organization(self, request, pk=None):
        """Remove this intervention type from an organization"""
        intervention_type = self.get_object()
        organization_id = request.data.get("organization_id")

        if not organization_id:
            return Response(
                {"error": "organization_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            organization = Organization.objects.get(id=organization_id)
            intervention_type.organizations.remove(organization)
            return Response(
                {
                    "message": f"Intervention type '{intervention_type.name}' removed from organization '{organization.organization_name}'"
                }
            )
        except Organization.DoesNotExist:
            return Response(
                {"error": "Organization not found"},
                status=status.HTTP_404_NOT_FOUND,
            )


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
    filterset_fields = ["intervention_type", "program"]
    search_fields = ["program__program_name", "intervention_type__name"]
    ordering_fields = ["created_at"]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == "retrieve":
            return ProgramInterventionDetailSerializer
        elif self.action == "create":
            return InterventionCreateSerializer
        return super().get_serializer_class()

    def perform_create(self, serializer):
        """Create intervention with fields"""
        data = serializer.validated_data
        fields_data = data.pop("fields", [])

        # Create the intervention
        intervention = ProgramIntervention.objects.create(
            intervention_type=data["intervention_type"], program=data["program"]
        )

        # Create fields and options
        for field_data in fields_data:
            options_data = field_data.pop("options", [])

            field = InterventionField.objects.create(
                intervention=intervention, **field_data
            )

            # Create options for this field
            for option_data in options_data:
                InterventionFieldOption.objects.create(field=field, **option_data)

        return intervention

    @action(detail=True, methods=["get"])
    def responses(self, request, pk=None):
        """Get responses for this intervention"""
        intervention = self.get_object()
        responses = intervention.intervention_responses.all()
        serializer = InterventionResponseSerializer(responses, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def add_response(self, request, pk=None):
        """Add a response to this intervention"""
        intervention = self.get_object()

        # Add intervention to request data
        request.data["intervention"] = intervention.id

        serializer = InterventionResponseCreateSerializer(data=request.data)
        if serializer.is_valid():
            data = serializer.validated_data
            answers_data = data.pop("answers", [])

            # Create the response
            response = InterventionResponse.objects.create(
                intervention=intervention,
                participant_id=data.get("participant_id"),
                patient_record=data.get("patient_record"),
            )

            # Create response values
            for answer_data in answers_data:
                InterventionResponseValue.objects.create(
                    participant=response,
                    field_id=answer_data["field"],
                    value=answer_data["value"],
                )

            return Response(
                {"message": "Response added successfully", "response_id": response.id},
                status=status.HTTP_201_CREATED,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

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
    def by_type(self, request):
        """Get interventions for a specific intervention type"""
        type_id = request.query_params.get("type_id")
        if not type_id:
            return Response(
                {"error": "type_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        queryset = self.get_queryset().filter(intervention_type_id=type_id)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def active(self, request):
        """Get interventions for active programs"""
        today = timezone.now().date()
        queryset = self.get_queryset().filter(
            program__status="in_progress",
            program__start_date__lte=today,
            program__end_date__gte=today,
        )
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def statistics(self, request, pk=None):
        """Get statistics for a specific intervention"""
        intervention = self.get_object()
        stats = {
            "total_responses": intervention.intervention_responses.count(),
            "total_fields": intervention.fields.count(),
            "required_fields": intervention.fields.filter(required=True).count(),
            "optional_fields": intervention.fields.filter(required=False).count(),
            "field_types": {
                "text": intervention.fields.filter(field_type="TEXT").count(),
                "number": intervention.fields.filter(field_type="NUMBER").count(),
                "date": intervention.fields.filter(field_type="DATE").count(),
            },
        }
        return Response(stats)


class InterventionResponseViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing intervention responses
    """

    queryset = InterventionResponse.objects.all()
    serializer_class = InterventionResponseSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["intervention", "patient_record"]
    search_fields = ["participant_id", "patient_record__first_name"]
    ordering_fields = ["date_created"]
    ordering = ["-date_created"]

    @action(detail=False, methods=["get"])
    def by_participant(self, request):
        """Get responses by participant ID"""
        participant_id = request.query_params.get("participant_id")
        if not participant_id:
            return Response(
                {"error": "participant_id parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        queryset = self.get_queryset().filter(participant_id=participant_id)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def by_patient(self, request):
        """Get responses by patient record"""
        patient_id = request.query_params.get("patient_id")
        if not patient_id:
            return Response(
                {"error": "patient_id parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        queryset = self.get_queryset().filter(patient_record_id=patient_id)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
