from rest_framework import viewsets, status, permissions, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.db.models import Count, Q, Sum
from datetime import timedelta
from django_filters import rest_framework as djangofilters
from helpers.functions import generate_reference_id
from accounts.models import CustomUser
from .models import (
    Organization,
    OrganizationFiles,
    HealthProgramType,
    HealthProgram,
    Participant,
    ProgramInterventionType,
    ProgramIntervention,
    InterventionField,
    InterventionFieldOption,
    InterventionResponse,
    InterventionResponseValue,
    BulkInterventionUpload,
    Survey,
    SurveyQuestionOption,
    SurveyQuestion,
    SurveyResponse,
    SurveyResponseAnswers,
    BulkSurveyUpload,
    LocumJobRole,
    LocumJob,
    LocumJobApplication,
    HealthProgramPartners,
    Staff,
)
from .serializers import (
    InterventionFieldSerializer,
    OrganizationCreateSerializer,
    OrganizationSerializer,
    HealthProgramTypeSerializer,
    HealthProgramSerializer,
    HealthProgramCreateSerializer,
    ProgramInterventionTypeSerializer,
    ProgramInterventionSerializer,
    ProgramInterventionDetailSerializer,
    InterventionCreateSerializer,
    InterventionResponseSerializer,
    InterventionResponseCreateSerializer,
    InterventionResponseUpdateSerializer,
    BulkInterventionUploadSerializer,
    RecentHealthProgramSerializer,
    SurveySerializer,
    SurveyResponseSerializer,
    BulkSurveyUploadSerializer,
    ProgramStatisticsSerializer,
    SurveyDetailSerializer,
    SurveyCreateSerializer,
    SurveyAnswerCreateSerializer,
    LocumJobRoleSerializer,
    LocumJobSerializer,
    LocumJobCreateSerializer,
    LocumJobDetailSerializer,
    LocumJobApplicationSerializer,
    HealthProgramPartnersSerializer,
    HealthProgramPartnersCreateSerializer,
    SurveyFormFieldsSerializer,
    StaffSerializer,
)
from rest_framework.views import APIView
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError
from helpers import exceptions
from accounts.tasks import generic_send_mail, generic_send_sms


class StaffViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing staff
    """

    queryset = Staff.objects.all()
    serializer_class = StaffSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        if self.action in ["list"]:
            permission_classes = [permissions.IsAdminUser]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]

    @transaction.atomic
    def perform_create(self, serializer):
        # check if user has organization profile
        if not hasattr(self.request.user, "community_profile"):
            raise ValidationError(
                {
                    "organization": "User must have an organization profile to create staff. "
                    "Please ensure the user is registered as a community organization."
                }
            )
        # get organization from authenticated user
        organization = self.request.user.community_profile
        # create a user account with the email
        user_account = CustomUser.objects.create(
            email=serializer.validated_data.get("email"),
            phone_number=serializer.validated_data.get("phone_number"),
            first_name=serializer.validated_data.get("first_name"),
            last_name=serializer.validated_data.get("last_name"),
        )
        # geenerate a temporary password and send it to ther user
        password = generate_reference_id()
        user_account.set_password(password)
        user_account.save()

        # send SMS and Email
        body = f"Dear User, Your account on {organization.organization_name} has been created successfully. Your temporary password is {password}"

        # sen SMS
        generic_send_sms.delay(
            to=str(user_account.phone_number),
            body=body,
        )

        # send Email
        payload = {
            "user_name": f"{user_account.first_name} {user_account.last_name}",
            "login_link": f"https://app.bridgecare.com/login?email={user_account.email}",
            "password": password,
            "email": user_account.email,
            "phone_number": str(user_account.phone_number),
            "organization_name": organization.organization_name,
        }
        generic_send_mail.delay(
            recipient=user_account.email,
            title="Account Created",
            payload=payload,
            email_type="staff_account_created",
        )

        # prepare to send email
        serializer.save(
            user_account=user_account,
            organization=organization,
        )


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
    def me(self, request, organization_id):
        """Get current user's organization profile"""
        if not hasattr(request.user, "community_profile"):
            raise exceptions.GeneralException(
                "Organization profile not found. Please ensure the user is registered as a community organization."
            )

        profile = request.user.community_profile
        serializer = self.get_serializer(profile)
        return Response(serializer.data)

    @action(detail=False, methods=["patch"])
    def update_my_profile(self, request):
        """Update current user's organization profile"""
        if not hasattr(request.user, "community_profile"):
            raise exceptions.GeneralException(
                "Organization profile not found. Please ensure the user is registered as a community organization."
            )

        profile = request.user.community_profile
        serializer = self.get_serializer(profile, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


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

    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == "create":
            return HealthProgramCreateSerializer
        return super().get_serializer_class()

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

        # Extract locum_job_ids from validated data
        locum_job_ids = serializer.validated_data.pop("locum_job_ids", [])

        # Create the health program
        program = serializer.save(created_by=user, organization=user.community_profile)

        # Create HealthProgramLocumNeed entries for each locum job
        if locum_job_ids:
            from .models import HealthProgramLocumNeed

            locum_needs = []
            for job_id in locum_job_ids:
                locum_needs.append(
                    HealthProgramLocumNeed(program=program, locum_job_id=job_id)
                )
            HealthProgramLocumNeed.objects.bulk_create(locum_needs)

        return program

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
    def upcoming(self, request, organization_id):
        """Get programs that are still in the planning stage"""
        _ = timezone.now().date()

        organization = Organization.objects.get(id=organization_id)
        queryset = HealthProgram.objects.filter(
            organization=organization, status="planning"
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

    @action(detail=True, methods=["post"])
    def approve(self, request, organization_id, pk=None):
        """Approve a health program with a reason"""
        program = self.get_object()

        if program.status != "planning":
            raise exceptions.GeneralException(
                "Only programs in planning stage can be approved"
            )

        approval_reason = request.data.get("approval_reason", "").strip()
        if not approval_reason:
            raise exceptions.GeneralException("Approval reason is required")

        program.status = "approved"
        program.approval_reason = approval_reason
        program.approved_by = request.user
        program.approved_at = timezone.now()
        program.save()

        return Response(
            {
                "message": "Program approved successfully",
                "approval_reason": approval_reason,
                "approved_by": request.user.email,
                "approved_at": program.approved_at,
            }
        )

    @action(detail=True, methods=["get"])
    def statistics(self, request, organization_id, pk=None):
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

    def perform_create(self, serializer):
        organization_id = self.kwargs.get("organization_id")
        organization = Organization.objects.get(id=organization_id)
        program_type = serializer.save()
        program_type.organizations.add(organization)
        program_type.save()
        return program_type

    def get_queryset(self):
        organization_id = self.kwargs.get("organization_id")
        return (
            super()
            .get_queryset()
            .filter(Q(organizations__id=organization_id) | Q(default=True))
        )

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

    @action(
        detail=True,
        methods=["get"],
        url_path="get-form-fields",
        url_name="get-form-fields",
    )
    def get_form_fields(self, request, organization_id, pk=None):
        """Get form fields for this survey"""
        survey = self.get_object()
        fields = survey.questions.all()
        serializer = SurveyFormFieldsSerializer(fields, many=True)
        return Response(serializer.data)

    @action(
        detail=True,
        methods=["get"],
        url_path="responses",
        url_name="responses",
    )
    def responses(self, request, organization_id, pk=None):
        """Get responses for this survey"""
        survey = self.get_object()
        responses = survey.responses.all()
        serializer = SurveyResponseSerializer(responses, many=True)
        return Response(serializer.data)


class SurveyCreateView(APIView):
    serializer_class = SurveyCreateSerializer

    @transaction.atomic
    def post(self, request, organization_id):
        organization = get_object_or_404(Organization, id=organization_id)
        if organization.user != request.user:
            raise ValidationError(
                "You are not authorized to create a survey for this organization."
            )
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
    def post(self, request, organization_id):

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
        return super().get_queryset().filter(survey_id=survey_id)


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
        _ = timezone.now().date()

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
    def post(self, request, organization_id):
        """Create intervention with fields and options"""
        organization = get_object_or_404(Organization, id=organization_id)

        serializer = InterventionCreateSerializer(
            data=request.data, context={"organization": organization}
        )
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        fields_data = data["fields"]
        program = data["program"]

        if program.organization_id != organization.id:
            raise ValidationError("Program does not belong to this organization.")

        # Create the intervention
        intervention = ProgramIntervention.objects.create(
            intervention_type=data["intervention_type"],
            program=program,
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
    def post(self, request, organization_id):
        """Submit intervention response with answers"""
        serializer = InterventionResponseCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        participant_data = data["participant"]
        answers_data = data["answers"]

        # Get intervention object
        intervention = data["intervention"]

        # create patient record
        fullname = participant_data["fullname"]
        phone_number = participant_data["phone_number"]
        if Participant.objects.filter(phone_number=phone_number).exists():
            participant = Participant.objects.get(phone_number=phone_number)
        else:
            participant = Participant.objects.create(
                fullname=fullname,
                phone_number=phone_number,
                gender=participant_data["gender"],
                email=participant_data["email"],
            )

        # Create intervention response
        response = InterventionResponse.objects.create(
            intervention=intervention,
            participant=participant,
        )

        # Create response values for each answer
        for answer_data in answers_data:
            InterventionResponseValue.objects.create(
                response=response,
                field_id=answer_data["field"],
                value=answer_data["value"],
            )

        # increase the participant counts on the program
        response.intervention.program.actual_participants += 1
        response.intervention.program.save()

        return Response(
            {
                "message": "Intervention response submitted successfully",
                "response_id": response.id,
                "answers_submitted": len(answers_data),
            },
            status=status.HTTP_201_CREATED,
        )


class InterventionAnswerUpdateView(APIView):
    """
    APIView for updating intervention responses
    """

    serializer_class = InterventionResponseUpdateSerializer
    permission_classes = [permissions.AllowAny]

    @transaction.atomic
    def put(self, request, response_id):
        response = get_object_or_404(InterventionResponse, id=response_id)

        serializer = InterventionResponseUpdateSerializer(
            data=request.data, context={"response": response}
        )
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        answers_data = data.get("answers")

        if "participant_id" in data:
            participant_id = data.get("participant_id")
            if isinstance(participant_id, str) and not participant_id.strip():
                participant_id = None
            response.participant_id = participant_id

        if "patient_record" in data:
            response.patient_record = data.get("patient_record")

        response.save()

        if answers_data is not None:
            for answer_data in answers_data:
                field = get_object_or_404(InterventionField, id=answer_data["field"])
                if field.intervention_id != response.intervention_id:
                    raise ValidationError("Field does not belong to this intervention.")
                InterventionResponseValue.objects.update_or_create(
                    participant=response,
                    field=field,
                    defaults={"value": answer_data["value"]},
                )

        return Response(
            InterventionResponseSerializer(response).data, status=status.HTTP_200_OK
        )

    @transaction.atomic
    def patch(self, request, response_id):
        return self.put(request, response_id)


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
    def responses(self, request, organization_id, pk=None):
        """Get responses for this intervention"""
        intervention = self.get_object()
        responses = intervention.intervention_responses.all()
        serializer = InterventionResponseSerializer(responses, many=True)
        return Response(serializer.data)

    @action(
        detail=True,
        methods=["get"],
        url_path="get-form-fields",
        url_name="get-form-fields",
    )
    def get_form_fields(self, request, organization_id, pk=None):
        """Get form fields for this intervention"""
        intervention = self.get_object()
        fields = intervention.fields.all()
        serializer = InterventionFieldSerializer(fields, many=True)
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


# Locum Job Views
class LocumJobRoleViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing locum job roles
    """

    queryset = LocumJobRole.objects.all()
    serializer_class = LocumJobRoleSerializer
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

    def get_queryset(self):
        """Filter queryset based on organization if provided"""
        organization_id = self.request.query_params.get("organization_id")
        if self.request.user.is_superuser:
            return super().get_queryset()
        else:
            return super().get_queryset().filter(organizations__id=organization_id)


class LocumJobViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing locum jobs
    """

    queryset = LocumJob.objects.all()
    serializer_class = LocumJobSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = [
        "role",
        "organization",
        "is_active",
        "approved",
        "renumeration_frequency",
    ]
    search_fields = [
        "title",
        "description",
        "location",
        "organization__organization_name",
    ]
    ordering_fields = ["date_created", "renumeration", "title"]
    ordering = ["-date_created"]

    def get_queryset(self):
        """Filter queryset based on organization if provided"""
        organization_id = self.request.query_params.get("organization_id")
        if self.request.user.is_superuser:
            return super().get_queryset()
        else:
            return super().get_queryset().filter(organizations__id=organization_id)

    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == "retrieve":
            return LocumJobDetailSerializer
        elif self.action == "create":
            return LocumJobCreateSerializer
        return super().get_serializer_class()

    @action(detail=True, methods=["get"])
    def statistics(self, request, pk=None):
        """Get statistics for a specific locum job"""
        job = self.get_object()
        stats = {
            "title": job.title,
            "organization": (
                job.organization.organization_name if job.organization else None
            ),
            "role": job.role.name if job.role else None,
            "renumeration": str(job.renumeration),
            "frequency": job.renumeration_frequency,
            "is_active": job.is_active,
            "approved": job.approved,
            "created_date": job.date_created,
            "last_updated": job.last_updated,
        }
        return Response(stats)


class LocumJobApplicationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing locum job applications
    """

    queryset = LocumJobApplication.objects.select_related(
        "job", "job__organization", "applicant"
    )
    serializer_class = LocumJobApplicationSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["job", "status"]
    search_fields = ["job__title", "full_name", "applicant__email"]
    ordering_fields = ["applied_at"]
    ordering = ["-applied_at"]

    def get_queryset(self):
        user = self.request.user
        queryset = super().get_queryset()
        if user.is_superuser:
            return queryset

        organization = getattr(user, "community_profile", None)
        if organization:
            return queryset.filter(job__organization=organization)

        return queryset.filter(applicant=user)

    def perform_create(self, serializer):
        job = serializer.validated_data["job"]
        user = self.request.user

        # check if the user has a health professional profile
        if not hasattr(user, "professional_profile"):
            raise exceptions.GeneralException(
                "Only registered health professionals can apply for locum jobs."
            )

        # check if job is active and approved
        if not job.is_active or not job.approved:
            raise ValidationError(
                "This job is not accepting applications at the moment."
            )

        if LocumJobApplication.objects.filter(
            job=job, applicant=self.request.user
        ).exists():
            raise ValidationError("You have already applied for this job.")

        full_name = (
            serializer.validated_data.get("full_name")
            or f"{self.request.user.first_name} {self.request.user.last_name}".strip()
            or self.request.user.email
        )
        email = serializer.validated_data.get("email") or self.request.user.email

        serializer.save(applicant=self.request.user, full_name=full_name, email=email)

    def retrieve(self, request, *args, **kwargs):
        """
        Retrieve a locum job application and automatically set status to under_review
        if it's currently submitted.
        """
        instance = self.get_object()

        # Automatically set status to under_review if it's currently submitted
        if instance.status == LocumJobApplication.STATUS_SUBMITTED:
            instance.status = LocumJobApplication.STATUS_UNDER_REVIEW
            instance.save(update_fields=["status"])

        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def perform_update(self, serializer):
        application = self.get_object()
        user = self.request.user

        if user.is_superuser or self._user_is_job_owner(application, user):
            serializer.save()
            return

        if application.applicant_id == user.id:
            serializer.validated_data.pop("status", None)
            serializer.save()
            return

        raise ValidationError("You are not allowed to update this application.")

    def perform_destroy(self, instance):
        if not self._user_can_manage_application(instance, self.request.user):
            raise ValidationError("You are not allowed to delete this application.")
        instance.delete()

    @action(detail=True, methods=["post"])
    def accept(self, request, organization_id, pk=None):
        """
        Accept a locum job application.
        Only job owners or superusers can accept applications.
        """
        application = self.get_object()
        user = request.user

        # TODO: notify applicant view email

        # Check if user has permission to accept (job owner or superuser)
        if not (user.is_superuser or self._user_is_job_owner(application, user)):
            raise exceptions.GeneralException(
                "You are not authorized to accept this application."
            )

        # Check if application can be accepted
        if application.status == LocumJobApplication.STATUS_ACCEPTED:
            raise exceptions.GeneralException("Application is already accepted.")

        # Update status to accepted
        application.status = LocumJobApplication.STATUS_ACCEPTED
        application.save(update_fields=["status"])

        serializer = self.get_serializer(application)
        return Response(
            {
                "message": "Application accepted successfully.",
                "application": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    def reject(
        self,
        request,
        organization_id,
        pk=None,
    ):
        """
        Reject a locum job application.
        Only job owners or superusers can reject applications.
        """
        application = self.get_object()
        user = request.user

        # TODO: notify applicant view email

        # Check if user has permission to reject (job owner or superuser)
        if not (user.is_superuser or self._user_is_job_owner(application, user)):
            raise exceptions.GeneralException(
                "You are not authorized to reject this application."
            )

        # Check if application can be rejected
        if application.status == LocumJobApplication.STATUS_REJECTED:
            raise exceptions.GeneralException("Application is already rejected.")

        # Update status to rejected
        application.status = LocumJobApplication.STATUS_REJECTED
        application.save(update_fields=["status"])

        serializer = self.get_serializer(application)
        return Response(
            {
                "message": "Application rejected successfully.",
                "application": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def _user_is_job_owner(self, application, user):
        organization = getattr(user, "community_profile", None)
        if not organization:
            return False
        return application.job.organization_id == organization.id

    def _user_can_manage_application(self, application, user):
        if user.is_superuser:
            return True
        if self._user_is_job_owner(application, user):
            return True
        return application.applicant_id == user.id


# Health Program Partners Views
class HealthProgramPartnersViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing health program partners
    """

    queryset = HealthProgramPartners.objects.all()
    serializer_class = HealthProgramPartnersSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    search_fields = ["name", "url"]
    ordering_fields = ["name", "date_created"]
    ordering = ["name"]

    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == "create":
            return HealthProgramPartnersCreateSerializer
        return super().get_serializer_class()

    def get_permissions(self):
        """Allow read access to all authenticated users, write access to admin users"""
        if self.action in ["list", "retrieve"]:
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [permissions.IsAdminUser]
        return [permission() for permission in permission_classes]


# Intervention Field Views
class InterventionFieldViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing intervention fields
    """

    queryset = InterventionField.objects.all()
    serializer_class = InterventionFieldSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["intervention"]
    search_fields = ["name"]
    http_method_names = ["get"]


class DashboardStatisticsView(APIView):
    """
    Dashboard overview for an organization's programs, interventions, and locum activity.
    """

    def get(self, request, organization_id=None, *args, **kwargs):
        organization_id = (
            organization_id
            or request.query_params.get("organization_id")
            or request.query_params.get("organization")
        )
        if not organization_id:
            raise exceptions.GeneralException("organization identifier is required.")

        organization = get_object_or_404(Organization, id=organization_id)

        data = {}
        now = timezone.now()
        current_week_start = (now - timedelta(days=now.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        next_week_start = current_week_start + timedelta(days=7)
        previous_week_start = current_week_start - timedelta(days=7)

        def range_filter_kwargs(field_name, start, end):
            return {
                f"{field_name}__gte": start,
                f"{field_name}__lt": end,
            }

        def weekly_counts(qs, field_name):
            current_value = qs.filter(
                **range_filter_kwargs(field_name, current_week_start, next_week_start)
            ).count()
            previous_value = qs.filter(
                **range_filter_kwargs(
                    field_name, previous_week_start, current_week_start
                )
            ).count()
            return current_value, previous_value

        def weekly_distinct_counts(qs, field_name, distinct_field):
            current_value = (
                qs.filter(
                    **range_filter_kwargs(
                        field_name, current_week_start, next_week_start
                    )
                )
                .values(distinct_field)
                .distinct()
                .count()
            )
            previous_value = (
                qs.filter(
                    **range_filter_kwargs(
                        field_name, previous_week_start, current_week_start
                    )
                )
                .values(distinct_field)
                .distinct()
                .count()
            )
            return current_value, previous_value

        def build_progress(label, value, week_current, week_previous):
            diff = week_current - week_previous
            if week_previous == 0:
                percentage = 100 if week_current > 0 else 0
            else:
                percentage = round((diff / week_previous) * 100, 2)
            direction = "up" if diff > 0 else "down" if diff < 0 else "flat"
            return {
                "label": label,
                "value": value,
                "week_current": week_current,
                "week_previous": week_previous,
                "change": {
                    "absolute": diff,
                    "percentage": percentage,
                    "direction": direction,
                    "comparison": "vs_last_week",
                },
            }

        # Active programs
        active_program_statuses = ["approved", "in_progress"]
        active_programs_qs = HealthProgram.objects.filter(
            organization=organization, status__in=active_program_statuses
        )
        data["active_programs"] = active_programs_qs.count()
        active_week_current, active_week_previous = weekly_counts(
            active_programs_qs, "created_at"
        )

        # Participants (distinct responders)
        participant_responses_qs = InterventionResponse.objects.filter(
            intervention__program__organization=organization
        ).exclude(participant__isnull=True)
        data["total_participant"] = (
            participant_responses_qs.values("participant_id").distinct().count()
        )
        participant_week_current, participant_week_previous = weekly_distinct_counts(
            participant_responses_qs, "date_created", "participant_id"
        )

        # Intervention responses
        intervention_responses_qs = InterventionResponse.objects.filter(
            intervention__program__organization=organization
        )
        data["total_interventions"] = intervention_responses_qs.count()
        intervention_week_current, intervention_week_previous = weekly_counts(
            intervention_responses_qs, "date_created"
        )

        # Partners
        partners_qs = HealthProgramPartners.objects.filter(
            health_programs_partners__organization=organization
        ).distinct()
        data["partners_recorded"] = partners_qs.count()
        partners_week_current = partners_qs.filter(
            **range_filter_kwargs(
                "health_programs_partners__created_at",
                current_week_start,
                next_week_start,
            )
        ).count()
        partners_week_previous = partners_qs.filter(
            **range_filter_kwargs(
                "health_programs_partners__created_at",
                previous_week_start,
                current_week_start,
            )
        ).count()

        # Locum bookings
        locum_applications_qs = LocumJobApplication.objects.filter(
            job__organization=organization
        )
        data["locum_booking"] = locum_applications_qs.count()
        locum_week_current, locum_week_previous = weekly_counts(
            locum_applications_qs, "applied_at"
        )

        # Program types summary
        program_types_queryset = (
            HealthProgramType.objects.filter(
                Q(default=True) | Q(organizations=organization)
            )
            .distinct()
            .order_by("name")
        )
        data["program_types"] = [
            {
                "name": program_type.name,
                "total": HealthProgram.objects.filter(
                    organization=organization, program_type=program_type
                ).count(),
            }
            for program_type in program_types_queryset
        ]

        # Age grouping placeholders (replace when analytics data is available)
        data["age-data"] = [
            {
                "age": "0-17",
                "count": 20,
            },
            {
                "age": "18-35",
                "count": 50,
            },
            {
                "age": "36-50",
                "count": 76,
            },
        ]

        # Intervention outcomes
        intervention_outcomes = []
        for intervention_type in ProgramInterventionType.objects.all():
            intervention_outcomes.append(
                {
                    "name": intervention_type.name,
                    "count": ProgramIntervention.objects.filter(
                        intervention_type=intervention_type
                    ).count(),
                }
            )
        data["intervention_outcomes"] = intervention_outcomes

        # Booking requests (recent applications)
        job_applications_qs = LocumJobApplication.objects.filter(
            job__organization=organization
        ).order_by("-applied_at")[:10]
        data["job_applications"] = LocumJobApplicationSerializer(
            instance=job_applications_qs, many=True, context={"request": request}
        ).data

        # Recent programs
        recent_programs_qs = HealthProgram.objects.filter(
            organization=organization, status__in=active_program_statuses
        ).order_by("-created_at")[:10]
        data["recent_programs"] = RecentHealthProgramSerializer(
            instance=recent_programs_qs, many=True, context={"request": request}
        ).data

        # Recent surveys (latest created)
        data["recent_surveys"] = SurveySerializer(
            instance=Survey.objects.all().order_by("-date_created")[:10],
            many=True,
            context={"request": request},
        ).data

        data["metrics_progress"] = [
            build_progress(
                "Active Programs",
                data["active_programs"],
                active_week_current,
                active_week_previous,
            ),
            build_progress(
                "Total Participants",
                data["total_participant"],
                participant_week_current,
                participant_week_previous,
            ),
            build_progress(
                "Interventions Logged",
                data["total_interventions"],
                intervention_week_current,
                intervention_week_previous,
            ),
            build_progress(
                "Total Partners",
                data["partners_recorded"],
                partners_week_current,
                partners_week_previous,
            ),
            build_progress(
                "Locum Applications",
                data["locum_booking"],
                locum_week_current,
                locum_week_previous,
            ),
        ]

        return Response(data=data, status=status.HTTP_200_OK)


# create a /me api endpoint that returns the community profile
