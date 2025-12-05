from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.views import APIView
from django.utils import timezone
from datetime import datetime, timedelta, date
from drf_spectacular.utils import extend_schema, OpenApiParameter
from helpers import exceptions
from patients.models import PatientProfile
from .models import (
    ProfessionalProfile,
    Profession,
    Specialization,
    LicenceIssueAuthority,
    AvailabilityBlock,
    BreakPeriod,
    Appointment,
)
from .serializers import (
    ProfessionalProfileSerializer,
    ProfessionsSerializer,
    SpecializationSerializer,
    LicenceIssueAuthoritySerializer,
    AppointmentSerializer,
    AppointmentCreateSerializer,
    AvailableTimeSlotSerializer,
    AvailableTimeSlotsQuerySerializer,
    AvailableTimeSlotsResponseSerializer,
)
from communities.serializers import LocumJobApplicationSerializer


class ProfessionsViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing professions
    """

    queryset = Profession.objects.filter(is_active=True)
    serializer_class = ProfessionsSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post"]


class SpecializationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing specializations
    """

    queryset = Specialization.objects.filter(is_active=True)
    serializer_class = SpecializationSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post"]


class LicenceIssueAuthorityViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing licence issue authorities
    """

    queryset = LicenceIssueAuthority.objects.filter(is_active=True)
    serializer_class = LicenceIssueAuthoritySerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post"]


class ProfessionalProfileViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing professional profiles
    """

    queryset = ProfessionalProfile.objects.all()
    serializer_class = ProfessionalProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
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
        "is_active",
    ]
    http_method_names = ["get", "post", "patch"]

    @action(detail=False, methods=["get"])
    def me(self, request):
        """Get current user's professional profile"""
        if not hasattr(request.user, "professional_profile"):
            raise exceptions.GeneralException(
                "Professional profile not found. Please ensure the user is registered as a health professional."
            )

        profile = request.user.professional_profile
        serializer = self.get_serializer(profile)
        return Response(serializer.data)


# get locum application of a the user
class LocumApplicationsView(APIView):
    serializer_class = LocumJobApplicationSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get"]

    def get(self, request):
        """Get locum applications of the user"""
        user = request.user
        applications = user.locum_job_applications.all()
        serializer = self.serializer_class(
            applications, many=True, context={"request": request}
        )
        return Response(serializer.data)


# =============================================================================
# APPOINTMENT BOOKING API ENDPOINTS
# =============================================================================


class AvailableTimeSlotsView(APIView):
    """
    API endpoint to get available time slots for a provider on a specific date.
    Returns all possible time slots with their availability status.
    """

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AvailableTimeSlotsQuerySerializer

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="provider_id",
                type={"type": "string", "format": "uuid"},
                location=OpenApiParameter.QUERY,
                required=True,
                description="The professional profile ID",
            ),
            OpenApiParameter(
                name="date",
                type={"type": "string", "format": "date"},
                location=OpenApiParameter.QUERY,
                required=True,
                description="The date to check availability (format: YYYY-MM-DD)",
            ),
        ],
        responses={200: AvailableTimeSlotsResponseSerializer},
    )
    def get(self, request):
        """Get available time slots for a provider on a specific date"""
        # Validate query parameters
        query_serializer = AvailableTimeSlotsQuerySerializer(data=request.query_params)
        if not query_serializer.is_valid():
            return Response(query_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        provider_id = query_serializer.validated_data["provider_id"]
        selected_date = query_serializer.validated_data["date"]

        # Get provider
        try:
            provider = ProfessionalProfile.objects.get(id=provider_id)
        except ProfessionalProfile.DoesNotExist:
            return Response(
                {"error": "Provider not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Get day of week
        day_of_week = selected_date.weekday()

        # Get availability blocks for this day
        availability_blocks = AvailabilityBlock.objects.filter(
            provider=provider, day_of_week=day_of_week
        ).order_by("start_time")

        if not availability_blocks.exists():
            return Response(
                {
                    "provider_id": str(provider.id),
                    "provider_name": f"{provider.user.first_name} {provider.user.last_name}".strip()
                    or provider.user.email,
                    "date": selected_date.isoformat(),
                    "time_slots": [],
                    "message": "No availability configured for this day",
                }
            )

        # Get existing appointments for this date
        existing_appointments = Appointment.objects.filter(
            provider=provider, date=selected_date
        )

        # Get all time slots
        all_time_slots = []

        for block in availability_blocks:
            # Get breaks for this block
            breaks = BreakPeriod.objects.filter(availability=block).order_by(
                "break_start"
            )

            # Generate time slots for this block
            current_time = block.start_time
            slot_duration = timedelta(minutes=block.slot_duration)

            while current_time < block.end_time:
                slot_end_time = (
                    datetime.combine(selected_date, current_time) + slot_duration
                ).time()

                # Check if slot would exceed block end time
                if slot_end_time > block.end_time:
                    break

                # Check if slot conflicts with breaks
                conflicts_with_break = False
                for break_period in breaks:
                    if (
                        current_time < break_period.break_end
                        and slot_end_time > break_period.break_start
                    ):
                        conflicts_with_break = True
                        break

                # Check if slot is booked
                is_booked = False
                for appointment in existing_appointments:
                    if (
                        current_time < appointment.end_time
                        and slot_end_time > appointment.start_time
                    ):
                        is_booked = True
                        break

                # Determine availability
                is_available = not conflicts_with_break and not is_booked

                # Only include slots that are not in the past (for today)
                if selected_date == date.today():
                    current_datetime = datetime.combine(selected_date, current_time)
                    if current_datetime <= timezone.now():
                        # Skip past slots
                        current_time = slot_end_time
                        continue

                all_time_slots.append(
                    {
                        "time": current_time.strftime("%H:%M:%S"),
                        "is_available": is_available,
                        "slot_duration": block.slot_duration,
                    }
                )

                # Move to next slot
                current_time = slot_end_time

        serializer = AvailableTimeSlotSerializer(all_time_slots, many=True)

        user = provider.user
        provider_name = (
            f"{user.first_name} {user.last_name}".strip()
            if (user.first_name or user.last_name)
            else user.email
        )

        return Response(
            {
                "provider_id": str(provider.id),
                "provider_name": provider_name,
                "date": selected_date.isoformat(),
                "time_slots": serializer.data,
            }
        )


class AppointmentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing appointments
    """

    queryset = Appointment.objects.all()
    serializer_class = AppointmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "patch"]


class AppointmentBookingView(APIView):
    """
    API endpoint for booking appointments
    """

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        request=AppointmentCreateSerializer,
        responses={201: AppointmentSerializer},
    )
    def post(self, request):
        """Create a new appointment booking"""
        serializer = AppointmentCreateSerializer(data=request.data)

        if serializer.is_valid():
            # get user's patient profile
            if not hasattr(request.user, "patient_profile"):
                patient_profile = PatientProfile.objects.get(user=request.user)
            else:
                patient_profile = request.user.patient_profile

            # check if patient already has an appointment on this same date and time
            if Appointment.objects.filter(
                patient=patient_profile, date=serializer.validated_data["date"]
            ).exists():
                raise exceptions.GeneralException(
                    "Sorry, you already have an appointment on this same date"
                )

            appointment = serializer.save(patient=patient_profile)

            response_serializer = AppointmentSerializer(appointment)
            return Response(
                {
                    "message": "Appointment booked successfully",
                    "appointment": response_serializer.data,
                },
                status=status.HTTP_201_CREATED,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
