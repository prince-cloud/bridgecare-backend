from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from django_filters import rest_framework as django_filters
from rest_framework.views import APIView
from django.utils import timezone
from django.db.models import Q
from datetime import datetime, timedelta, date
from drf_spectacular.utils import extend_schema, OpenApiParameter
from helpers import exceptions
from patients.models import PatientProfile, PatientAccess, Prescription, Visitation
from patients.serializers import PatientProfileListSerializer
from .models import (
    EducationHistory,
    ProfessionalProfile,
    Profession,
    Specialization,
    LicenceIssueAuthority,
    Availability,
    AvailabilityBlock,
    BreakPeriod,
    Appointment,
)
from .serializers import (
    EducationHistorySerializer,
    ProfessionalProfileSerializer,
    ProfessionsSerializer,
    SpecializationSerializer,
    LicenceIssueAuthoritySerializer,
    AppointmentSerializer,
    AppointmentCreateSerializer,
    AvailableTimeSlotSerializer,
    AvailableTimeSlotsQuerySerializer,
    AvailableTimeSlotsResponseSerializer,
    AppointmentStatusChangeSerializer,
    AppointmentRescheduleSerializer,
    PatientAppointmentActionSerializer,
    AvailabilitySerializer,
    AvailabilityBlockSerializer,
    BreakPeriodSerializer,
)
from communities.serializers import (
    LocumJobApplicationSerializer,
    HealthProgramInvitationSerializer,
    HealthProgramSerializer,
    ProgramInterventionSerializer,
)
from communities.models import (
    LocumJobApplication,
    HealthProgramInvitation,
    HealthProgram,
)
from .permissions import ProfessionalProfileRequired
from accounts.tasks import generic_send_mail


class ProfessionsViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing professions
    """

    queryset = Profession.objects.filter(is_active=True)
    serializer_class = ProfessionsSerializer
    # permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post"]


class SpecializationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing specializations
    """

    queryset = Specialization.objects.filter(is_active=True)
    serializer_class = SpecializationSerializer
    # permission_classes = [permissions.IsAuthenticated]
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
        "is_verified",
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

    @action(detail=False, methods=["get"])
    def search(self, request):
        """
        Search professional profiles by email, first name, last name, and phone number.
        Query parameter: 'q' - search term
        """
        search_term = request.query_params.get("q", "").strip()

        if not search_term:
            return Response(
                {"error": "Search term 'q' is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Build Q object to search across user fields
        query = (
            Q(user__email__icontains=search_term)
            | Q(user__first_name__icontains=search_term)
            | Q(user__last_name__icontains=search_term)
            | Q(user__phone_number__icontains=search_term)
        )

        # Also search for full name (first_name + last_name)
        # Split search term and search for combinations
        search_parts = search_term.split()
        if len(search_parts) > 1:
            # If multiple words, try matching first_name and last_name
            query |= Q(
                user__first_name__icontains=search_parts[0],
                user__last_name__icontains=search_parts[-1],
            ) | Q(
                user__first_name__icontains=search_parts[-1],
                user__last_name__icontains=search_parts[0],
            )

        # Filter queryset
        queryset = self.get_queryset().filter(query).distinct()

        # Paginate results
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


# =============================================================================
# AVAILABILITY MANAGEMENT VIEWSETS
# =============================================================================


class AvailabilityView(APIView):
    """
    API endpoint for managing provider availability preferences.
    Supports GET (retrieve) and PATCH (partial update/create) operations.
    Since it's a OneToOne relationship, it will create if doesn't exist, or update if it exists.
    """

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AvailabilitySerializer

    @extend_schema(
        responses={200: AvailabilitySerializer},
        summary="Get availability preferences",
        description="Get the current user's availability preferences. Returns default values if not set.",
    )
    def get(self, request):
        """Get or create availability preferences for current user"""
        user = request.user

        if not hasattr(user, "professional_profile"):
            raise exceptions.GeneralException(
                "Professional profile not found. Please ensure the user is registered as a health professional."
            )

        professional_profile = user.professional_profile

        # Get or create availability
        availability, created = Availability.objects.get_or_create(
            provider=professional_profile,
            defaults={
                "patient_visit_availability": False,
                "provider_visit_availability": False,
                "telehealth_availability": False,
            },
        )

        serializer = self.serializer_class(availability)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        request=AvailabilitySerializer,
        responses={200: AvailabilitySerializer},
        summary="Update availability preferences",
        description="Partially update availability preferences for the current user. Creates if doesn't exist, updates if exists.",
    )
    def patch(self, request):
        """Partially update or create availability preferences"""
        user = request.user

        if not hasattr(user, "professional_profile"):
            raise exceptions.GeneralException(
                "Professional profile not found. Please ensure the user is registered as a health professional."
            )

        professional_profile = user.professional_profile

        # Get or create availability
        availability, created = Availability.objects.get_or_create(
            provider=professional_profile,
            defaults={
                "patient_visit_availability": False,
                "provider_visit_availability": False,
                "telehealth_availability": False,
            },
        )

        serializer = self.serializer_class(
            availability, data=request.data, partial=True
        )
        if serializer.is_valid():
            serializer.save(provider=professional_profile)
            return Response(
                serializer.data,
                status=status.HTTP_200_OK if not created else status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AvailabilityBlockViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing availability blocks
    Providers can manage their own availability schedules
    """

    queryset = AvailabilityBlock.objects.all()
    serializer_class = AvailabilityBlockSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["provider", "day_of_week"]
    ordering_fields = ["day_of_week", "start_time"]
    ordering = ["day_of_week", "start_time"]
    http_method_names = ["get", "post", "patch", "delete"]

    def get_queryset(self):
        """Filter to show only current provider's availability blocks"""
        queryset = AvailabilityBlock.objects.all()
        user = self.request.user

        # If user is a professional, filter by their profile
        if hasattr(user, "professional_profile"):
            queryset = queryset.filter(provider=user.professional_profile)
        # Allow staff/admin to see all
        elif not (user.is_staff or user.is_superuser):
            # Regular users see none
            queryset = queryset.none()

        return queryset

    def perform_create(self, serializer):
        """Set provider to current user's professional profile"""
        user = self.request.user

        if not hasattr(user, "professional_profile"):
            raise exceptions.GeneralException(
                "Professional profile not found. Please ensure the user is registered as a health professional."
            )

        # Check if user is trying to set a different provider
        provider = serializer.validated_data.get("provider")
        if provider and provider != user.professional_profile:
            # Allow only if user is staff/admin
            if not (user.is_staff or user.is_superuser):
                raise exceptions.GeneralException(
                    "You can only create availability blocks for your own profile."
                )

        # Auto-set provider if not provided or if user is not staff/admin
        if not provider or (not user.is_staff and not user.is_superuser):
            serializer.save(provider=user.professional_profile)
        else:
            serializer.save()

    def perform_update(self, serializer):
        """Ensure provider can only update their own availability blocks"""
        user = self.request.user
        instance = self.get_object()

        # Check if user owns this availability block
        if instance.provider.user != user:
            if not (user.is_staff or user.is_superuser):
                raise exceptions.GeneralException(
                    "You can only update your own availability blocks."
                )

        # Prevent changing provider unless staff/admin
        provider = serializer.validated_data.get("provider")
        if provider and provider != instance.provider:
            if not (user.is_staff or user.is_superuser):
                raise exceptions.GeneralException(
                    "You cannot change the provider of an availability block."
                )

        serializer.save()

    def perform_destroy(self, instance):
        """Ensure provider can only delete their own availability blocks"""
        user = self.request.user

        if instance.provider.user != user:
            if not (user.is_staff or user.is_superuser):
                raise exceptions.GeneralException(
                    "You can only delete your own availability blocks."
                )

        instance.delete()


class BreakPeriodViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing break periods within availability blocks
    Providers can manage breaks in their availability blocks
    """

    queryset = BreakPeriod.objects.all()
    serializer_class = BreakPeriodSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["availability"]
    ordering_fields = ["break_start"]
    ordering = ["break_start"]
    http_method_names = ["get", "post", "patch", "delete"]

    def get_queryset(self):
        """Filter to show only breaks for current provider's availability blocks"""
        queryset = BreakPeriod.objects.all()
        user = self.request.user

        # If user is a professional, filter by their availability blocks
        if hasattr(user, "professional_profile"):
            queryset = queryset.filter(availability__provider=user.professional_profile)
        # Allow staff/admin to see all
        elif not (user.is_staff or user.is_superuser):
            # Regular users see none
            queryset = queryset.none()

        return queryset

    def perform_create(self, serializer):
        """Ensure break is added to provider's own availability block"""
        user = self.request.user
        availability = serializer.validated_data.get("availability")

        if not availability:
            raise exceptions.GeneralException("Availability block is required.")

        # Check if user owns this availability block
        if availability.provider.user != user:
            if not (user.is_staff or user.is_superuser):
                raise exceptions.GeneralException(
                    "You can only add breaks to your own availability blocks."
                )

        serializer.save()

    def perform_update(self, serializer):
        """Ensure provider can only update breaks in their own availability blocks"""
        user = self.request.user
        instance = self.get_object()

        # Check if user owns the availability block
        if instance.availability.provider.user != user:
            if not (user.is_staff or user.is_superuser):
                raise exceptions.GeneralException(
                    "You can only update breaks in your own availability blocks."
                )

        # Check if trying to change to a different availability block
        availability = serializer.validated_data.get("availability")
        if availability and availability != instance.availability:
            if availability.provider.user != user:
                if not (user.is_staff or user.is_superuser):
                    raise exceptions.GeneralException(
                        "You cannot move breaks to availability blocks you don't own."
                    )

        serializer.save()

    def perform_destroy(self, instance):
        """Ensure provider can only delete breaks in their own availability blocks"""
        user = self.request.user

        if instance.availability.provider.user != user:
            if not (user.is_staff or user.is_superuser):
                raise exceptions.GeneralException(
                    "You can only delete breaks in your own availability blocks."
                )

        instance.delete()


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


class AppointmentFilter(django_filters.FilterSet):
    """
    Custom filter set for Appointment that supports date range filtering
    """

    start_date = django_filters.DateFilter(field_name="date", lookup_expr="gte")
    end_date = django_filters.DateFilter(field_name="date", lookup_expr="lte")

    class Meta:
        model = Appointment
        fields = ["start_date", "end_date"]


class AppointmentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing appointments
    """

    queryset = Appointment.objects.all()
    serializer_class = AppointmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post"]
    filter_backends = [DjangoFilterBackend]
    filterset_class = AppointmentFilter

    def get_queryset(self):
        """Get queryset for the view"""
        queryset = super().get_queryset()
        user = self.request.user
        if not (user.is_staff or user.is_superuser):
            if hasattr(user, "professional_profile"):
                queryset = queryset.filter(provider=user.professional_profile)
            elif hasattr(user, "patient_profile"):
                queryset = queryset.filter(patient=user.patient_profile)
            else:
                queryset = queryset.none()
        return queryset

    @extend_schema(
        responses={200: AppointmentSerializer},
        summary="Confirm appointment",
        description="Confirm a pending appointment. Only the provider, staff, or admin can confirm appointments.",
    )
    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        """Confirm an appointment"""
        appointment = self.get_object()

        # Check if user is the provider or has permission
        if not (
            appointment.provider.user == request.user
            or request.user.is_staff
            or request.user.is_superuser
        ):
            raise exceptions.GeneralException(
                "You do not have permission to confirm this appointment."
            )

        # Check if appointment can be confirmed
        if appointment.status == Appointment.Status.CONFIRMED:
            raise exceptions.GeneralException("Appointment is already confirmed.")

        if appointment.status == Appointment.Status.CANCELLED:
            raise exceptions.GeneralException("Cannot confirm a cancelled appointment.")

        if appointment.status == Appointment.Status.COMPLETED:
            raise exceptions.GeneralException("Cannot confirm a completed appointment.")

        # Update appointment status
        appointment.status = Appointment.Status.CONFIRMED
        appointment.save()

        serializer = self.get_serializer(appointment)

        # TODO: send appointment confirmed email to patient and provider

        return Response(
            {
                "message": "Appointment confirmed successfully",
                "appointment": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=AppointmentStatusChangeSerializer,
        responses={200: AppointmentSerializer},
        summary="Change appointment status",
    )
    @action(detail=True, methods=["post"])
    def change_status(self, request, pk=None):
        """Change appointment status from confirmed to another status"""
        appointment = self.get_object()

        # Check if user is the provider or has permission
        if not (
            appointment.provider.user == request.user
            or request.user.is_staff
            or request.user.is_superuser
        ):
            raise exceptions.GeneralException(
                "You do not have permission to change this appointment's status."
            )

        serializer = AppointmentStatusChangeSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        new_status = serializer.validated_data["status"]
        current_status = appointment.status

        # Validate status transition
        # Only allow changing from CONFIRMED status
        if current_status != Appointment.Status.CONFIRMED:
            raise exceptions.GeneralException(
                f"Cannot change status. Current status is {current_status}. Only appointments with CONFIRMED status can have their status changed."
            )

        # Validate new status is one of the allowed statuses
        allowed_statuses = [
            Appointment.Status.COMPLETED,
            Appointment.Status.NO_SHOW,
            Appointment.Status.CANCELLED,
        ]
        if new_status not in [status.value for status in allowed_statuses]:
            raise exceptions.GeneralException(
                "Invalid status. Can only change to: COMPLETED, NO_SHOW, or CANCELLED"
            )

        # Check if already in the requested status
        if current_status == new_status:
            status_label = dict(Appointment.Status.choices).get(new_status, new_status)
            raise exceptions.GeneralException(f"Appointment is already {status_label}.")

        # Update appointment status
        appointment.status = new_status
        comment = serializer.validated_data.get("comment", "")
        if comment:
            # Store comment in reason field or use for notification
            if appointment.reason:
                appointment.reason = (
                    f"{appointment.reason}\n\n[Status Change Comment]: {comment}"
                )
            else:
                appointment.reason = f"[Status Change Comment]: {comment}"
        appointment.save()

        serializer_response = self.get_serializer(appointment)
        status_label = dict(Appointment.Status.choices).get(new_status, new_status)

        # TODO: send status change email to patient and provider with comment

        return Response(
            {
                "message": f"Appointment status changed to {status_label} successfully",
                "appointment": serializer_response.data,
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=AppointmentRescheduleSerializer,
        responses={200: AppointmentSerializer},
        summary="Reschedule appointment",
        description="Reschedule an appointment with a new date and time. Only the provider, staff, or admin can reschedule appointments.",
    )
    @action(detail=True, methods=["post"])
    def reschedule(self, request, pk=None):
        """Reschedule an appointment with new date and time"""
        appointment = self.get_object()

        # Check if user is the provider or has permission
        if not (
            appointment.provider.user == request.user
            or request.user.is_staff
            or request.user.is_superuser
        ):
            raise exceptions.GeneralException(
                "You do not have permission to reschedule this appointment."
            )

        # Validate that appointment can be rescheduled
        if appointment.status == Appointment.Status.COMPLETED:
            raise exceptions.GeneralException(
                "Cannot reschedule a completed appointment."
            )

        if appointment.status == Appointment.Status.CANCELLED:
            raise exceptions.GeneralException(
                "Cannot reschedule a cancelled appointment."
            )

        serializer = AppointmentRescheduleSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        new_date = serializer.validated_data["date"]
        new_start_time = serializer.validated_data["start_time"]
        provider = appointment.provider

        # Validate new date and time (reuse logic from AppointmentCreateSerializer)
        # Get day of week
        day_of_week = new_date.weekday()

        # Check if provider has availability for this day
        availability_blocks = AvailabilityBlock.objects.filter(
            provider=provider, day_of_week=day_of_week
        )

        if not availability_blocks.exists():
            raise exceptions.GeneralException("Provider is not available on this day.")

        # Check if start_time falls within any availability block
        time_within_availability = False
        slot_duration = None
        matching_block = None

        for block in availability_blocks:
            if block.start_time <= new_start_time < block.end_time:
                slot_duration = block.slot_duration
                time_within_availability = True
                matching_block = block
                break

        if not time_within_availability:
            raise exceptions.GeneralException(
                "Start time is outside provider's availability hours."
            )

        # Check for breaks in the matching block
        breaks = BreakPeriod.objects.filter(availability=matching_block)
        for break_period in breaks:
            if break_period.break_start <= new_start_time < break_period.break_end:
                raise exceptions.GeneralException(
                    "Start time conflicts with provider's break period."
                )

        # Calculate end_time
        start_datetime = datetime.combine(new_date, new_start_time)
        end_datetime = start_datetime + timedelta(minutes=slot_duration)
        new_end_time = end_datetime.time()

        # Check if end_time conflicts with breaks
        for break_period in breaks:
            if (
                new_start_time < break_period.break_end
                and new_end_time > break_period.break_start
            ):
                raise exceptions.GeneralException(
                    "Appointment time conflicts with provider's break period."
                )

        # Check if slot is already booked (exclude current appointment)
        conflicting_appointments = (
            Appointment.objects.filter(
                provider=provider,
                date=new_date,
            )
            .exclude(id=appointment.id)
            .exclude(start_time__gte=new_end_time)
            .exclude(end_time__lte=new_start_time)
        )

        if conflicting_appointments.exists():
            raise exceptions.GeneralException(
                "This time slot is already booked. Please choose another time."
            )

        # Update appointment
        appointment.date = new_date
        appointment.start_time = new_start_time
        appointment.end_time = new_end_time
        appointment.status = Appointment.Status.RESCHEDULED
        comment = serializer.validated_data.get("comment", "")
        if comment:
            # Store comment in reason field or use for notification
            if appointment.reason:
                appointment.reason = (
                    f"{appointment.reason}\n\n[Reschedule Comment]: {comment}"
                )
            else:
                appointment.reason = f"[Reschedule Comment]: {comment}"
        appointment.save()

        serializer_response = self.get_serializer(appointment)

        # TODO: send reschedule email to patient and provider with comment

        return Response(
            {
                "message": "Appointment rescheduled successfully",
                "appointment": serializer_response.data,
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=PatientAppointmentActionSerializer,
        responses={200: AppointmentSerializer},
        summary="Patient appointment action",
        description="Patients can reschedule pending appointments or cancel confirmed appointments (at least 2 days before appointment date).",
    )
    @action(detail=True, methods=["post"])
    def patient_action(self, request, pk=None):
        """Patient action: reschedule pending appointments or cancel confirmed appointments"""
        appointment = self.get_object()

        # Check if user is the patient
        patient_profile = None
        if hasattr(request.user, "patient_profile"):
            patient_profile = request.user.patient_profile
        else:
            try:
                patient_profile = PatientProfile.objects.get(user=request.user)
            except PatientProfile.DoesNotExist:
                raise exceptions.GeneralException(
                    "Patient profile not found. Only patients can perform this action."
                )

        if appointment.patient != patient_profile:
            raise exceptions.GeneralException(
                "You can only perform actions on your own appointments."
            )

        serializer = PatientAppointmentActionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        action = serializer.validated_data["action"]
        comment = serializer.validated_data.get("comment", "")
        current_status = appointment.status

        if action == "reschedule":
            # Patient can only reschedule PENDING appointments
            if current_status != Appointment.Status.PENDING:
                raise exceptions.GeneralException(
                    "You can only reschedule appointments with PENDING status."
                )

            # Validate required fields for rescheduling
            new_date = serializer.validated_data.get("date")
            new_start_time = serializer.validated_data.get("start_time")

            if not new_date or not new_start_time:
                raise exceptions.GeneralException(
                    "Both 'date' and 'start_time' are required for rescheduling."
                )

            provider = appointment.provider

            # Validate new date and time (reuse logic from reschedule action)
            day_of_week = new_date.weekday()

            # Check if provider has availability for this day
            availability_blocks = AvailabilityBlock.objects.filter(
                provider=provider, day_of_week=day_of_week
            )

            if not availability_blocks.exists():
                raise exceptions.GeneralException(
                    "Provider is not available on this day."
                )

            # Check if start_time falls within any availability block
            time_within_availability = False
            slot_duration = None
            matching_block = None

            for block in availability_blocks:
                if block.start_time <= new_start_time < block.end_time:
                    slot_duration = block.slot_duration
                    time_within_availability = True
                    matching_block = block
                    break

            if not time_within_availability:
                raise exceptions.GeneralException(
                    "Start time is outside provider's availability hours."
                )

            # Check for breaks in the matching block
            breaks = BreakPeriod.objects.filter(availability=matching_block)
            for break_period in breaks:
                if break_period.break_start <= new_start_time < break_period.break_end:
                    raise exceptions.GeneralException(
                        "Start time conflicts with provider's break period."
                    )

            # Calculate end_time
            start_datetime = datetime.combine(new_date, new_start_time)
            end_datetime = start_datetime + timedelta(minutes=slot_duration)
            new_end_time = end_datetime.time()

            # Check if end_time conflicts with breaks
            for break_period in breaks:
                if (
                    new_start_time < break_period.break_end
                    and new_end_time > break_period.break_start
                ):
                    raise exceptions.GeneralException(
                        "Appointment time conflicts with provider's break period."
                    )

            # Check if slot is already booked (exclude current appointment)
            conflicting_appointments = (
                Appointment.objects.filter(
                    provider=provider,
                    date=new_date,
                )
                .exclude(id=appointment.id)
                .exclude(start_time__gte=new_end_time)
                .exclude(end_time__lte=new_start_time)
            )

            if conflicting_appointments.exists():
                raise exceptions.GeneralException(
                    "This time slot is already booked. Please choose another time."
                )

            # Update appointment
            appointment.date = new_date
            appointment.start_time = new_start_time
            appointment.end_time = new_end_time
            appointment.status = Appointment.Status.RESCHEDULED
            if comment:
                if appointment.reason:
                    appointment.reason = f"{appointment.reason}\n\n[Patient Reschedule Comment]: {comment}"
                else:
                    appointment.reason = f"[Patient Reschedule Comment]: {comment}"
            appointment.save()

            message = "Appointment rescheduled successfully"

        elif action == "cancel":
            # Patient can only cancel CONFIRMED appointments
            if current_status != Appointment.Status.CONFIRMED:
                raise exceptions.GeneralException(
                    "You can only cancel appointments with CONFIRMED status."
                )

            # Check if cancellation is at least 2 days before appointment date
            appointment_datetime = datetime.combine(
                appointment.date, appointment.start_time
            )
            days_before = (appointment_datetime.date() - date.today()).days

            if days_before < 2:
                raise exceptions.GeneralException(
                    f"Cannot cancel appointment. You can only cancel confirmed appointments at least 2 days before the appointment date. Your appointment is in {days_before} day(s)."
                )

            # Update appointment status
            appointment.status = Appointment.Status.CANCELLED
            if comment:
                if appointment.reason:
                    appointment.reason = f"{appointment.reason}\n\n[Patient Cancellation Comment]: {comment}"
                else:
                    appointment.reason = f"[Patient Cancellation Comment]: {comment}"
            appointment.save()

            message = "Appointment cancelled successfully"

        else:
            raise exceptions.GeneralException(f"Invalid action: {action}")

        serializer_response = self.get_serializer(appointment)

        # TODO: send notification email to patient and provider with comment

        return Response(
            {
                "message": message,
                "appointment": serializer_response.data,
            },
            status=status.HTTP_200_OK,
        )


class AppointmentBookingView(APIView):
    """
    API endpoint for booking appointments
    """

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AppointmentCreateSerializer

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
                raise exceptions.GeneralException(
                    "You must have a patient profile to book an appointment."
                )
            else:
                patient_profile = request.user.patient_profile

                print("=== patient_profile: ", patient_profile)

            # check if patient already has an appointment on this same date and time
            print("==== date: ", serializer.validated_data["date"])
            if Appointment.objects.filter(
                patient=patient_profile, date=serializer.validated_data["date"]
            ).exists():
                raise exceptions.GeneralException(
                    "Sorry, you already have an appointment on this same date"
                )

            appointment = serializer.save(patient=patient_profile)

            # TODO: send appointment booked email to patient and provider

            response_serializer = AppointmentSerializer(appointment)

            # after creating the appointment, create a patient access record
            PatientAccess.objects.create(
                patient=patient_profile,
                health_professional=appointment.provider,
                is_active=True,
            )

            return Response(
                {
                    "message": "Appointment booked successfully",
                    "appointment": response_serializer.data,
                },
                status=status.HTTP_201_CREATED,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PatientView(APIView):
    """View for patients"""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = PatientProfileListSerializer

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="search",
                type={"type": "string"},
                location=OpenApiParameter.QUERY,
                required=False,
                description="Search term to filter patients",
            ),
            OpenApiParameter(
                name="search_type",
                type={"type": "string"},
                location=OpenApiParameter.QUERY,
                required=False,
                enum=["patient_id", "general"],
                description="Type of search: 'patient_id' for exact match on patient ID, 'general' for partial match on first_name, last_name, email, or phone_number (searches both PatientProfile and User model fields)",
            ),
        ],
        responses={200: PatientProfileListSerializer(many=True)},
    )
    def get(self, request):
        """
        Get all patients. Optionally filter by search query parameter.
        - If search_type is 'patient_id', performs exact match on patient_id
        - If search_type is 'general' or not provided, performs partial match (icontains) on first_name, last_name, email, and phone_number from both PatientProfile and User model
        """
        user = request.user
        if not hasattr(user, "professional_profile"):
            raise exceptions.GeneralException(
                "You are not authorized to access this resource."
            )
        professional_profile = user.professional_profile

        # Get patient IDs from PatientAccess objects
        patient_ids = professional_profile.patient_access.filter(
            is_active=True
        ).values_list("patient_id", flat=True)

        # Get the actual PatientProfile objects
        patient_profiles = PatientProfile.objects.filter(id__in=patient_ids)

        # Get search parameters
        search_query = request.query_params.get("search")
        search_type = request.query_params.get("search_type", "general")

        # Apply search filters if search query is provided
        if search_query:
            search_query = search_query.strip()

            if search_type == "patient_id":
                # Exact match on patient_id
                patient_profiles = patient_profiles.filter(patient_id=search_query)
                if not patient_profiles.exists():
                    raise exceptions.GeneralException(
                        f"Patient with ID '{search_query}' not found or you don't have access to this patient."
                    )
            else:
                # General search with icontains on first_name, last_name, email, and phone_number
                # Searches both PatientProfile fields and related User model fields
                search_filter = (
                    Q(first_name__icontains=search_query)
                    | Q(last_name__icontains=search_query)
                    | Q(email__icontains=search_query)
                    | Q(phone_number__icontains=search_query)
                    | Q(user__first_name__icontains=search_query)
                    | Q(user__last_name__icontains=search_query)
                    | Q(user__email__icontains=search_query)
                    | Q(user__phone_number__icontains=search_query)
                )
                patient_profiles = patient_profiles.filter(search_filter)

                if not patient_profiles.exists():
                    raise exceptions.GeneralException(
                        f"No patients found matching '{search_query}'"
                    )

        # Paginate the results
        paginator = PageNumberPagination()
        paginator.page_size = 64  # Match default page size from settings
        paginated_queryset = paginator.paginate_queryset(patient_profiles, request)

        serializer = self.serializer_class(paginated_queryset, many=True)
        return paginator.get_paginated_response(serializer.data)


class DashboardStatisticsView(APIView):
    """
    Dashboard overview for a professional's patients, prescriptions, appointments, and locum activity.
    """

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        responses={200: dict},
        summary="Get professional dashboard statistics",
        description="Get dashboard statistics for the current professional including patients, prescriptions, appointments, and locum applications",
    )
    def get(self, request, *args, **kwargs):
        """Get dashboard statistics for the current professional"""
        user = request.user

        if not hasattr(user, "professional_profile"):
            raise exceptions.GeneralException(
                "Professional profile not found. Please ensure the user is registered as a health professional."
            )

        professional_profile = user.professional_profile

        data = {}
        now = timezone.now()
        today = date.today()
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

        # Total Patients (from PatientAccess)
        patients_qs = PatientAccess.objects.filter(
            health_professional=professional_profile, is_active=True
        )
        data["total_patients"] = patients_qs.count()
        patients_week_current, patients_week_previous = weekly_counts(
            patients_qs, "created_at"
        )

        # Patient Age Distribution
        patient_accesses = PatientAccess.objects.filter(
            health_professional=professional_profile, is_active=True
        ).select_related("patient")

        age_groups = {
            "0-17": 0,
            "18-35": 0,
            "36-50": 0,
            "51-65": 0,
            "65+": 0,
        }

        total_patients_with_dob = 0

        for patient_access in patient_accesses:
            patient = patient_access.patient
            if patient.date_of_birth:
                # Calculate age
                today = date.today()
                age = (
                    today.year
                    - patient.date_of_birth.year
                    - (
                        (today.month, today.day)
                        < (patient.date_of_birth.month, patient.date_of_birth.day)
                    )
                )

                total_patients_with_dob += 1

                # Categorize into age groups
                if age <= 17:
                    age_groups["0-17"] += 1
                elif 18 <= age <= 35:
                    age_groups["18-35"] += 1
                elif 36 <= age <= 50:
                    age_groups["36-50"] += 1
                elif 51 <= age <= 65:
                    age_groups["51-65"] += 1
                else:  # age > 65
                    age_groups["65+"] += 1

        # Calculate percentages and format age distribution data
        # Maintain specific order for age ranges
        age_range_order = ["0-17", "18-35", "36-50", "51-65", "65+"]
        age_distribution = []
        for age_range in age_range_order:
            count = age_groups[age_range]
            percentage = (
                round((count / total_patients_with_dob * 100), 2)
                if total_patients_with_dob > 0
                else 0
            )
            age_distribution.append(
                {
                    "age_range": age_range,
                    "count": count,
                    "percentage": percentage,
                }
            )

        data["age_distribution"] = age_distribution
        data["total_patients_with_age_data"] = total_patients_with_dob

        # Total Prescriptions (from Visitation's Prescriptions)
        prescriptions_qs = Prescription.objects.filter(
            visitation__issued_by=professional_profile
        )
        data["total_prescriptions"] = prescriptions_qs.count()
        prescriptions_week_current, prescriptions_week_previous = weekly_counts(
            prescriptions_qs, "date_created"
        )

        # Active Appointments (CONFIRMED and PENDING status)
        active_appointment_statuses = [
            Appointment.Status.CONFIRMED,
            Appointment.Status.PENDING,
        ]
        active_appointments_qs = Appointment.objects.filter(
            provider=professional_profile, status__in=active_appointment_statuses
        )
        data["active_appointments"] = active_appointments_qs.count()
        active_appointments_week_current, active_appointments_week_previous = (
            weekly_counts(active_appointments_qs, "created_at")
        )

        # Active Locum Applications (non-rejected applications)
        active_locum_statuses = [
            LocumJobApplication.STATUS_SUBMITTED,
            LocumJobApplication.STATUS_UNDER_REVIEW,
            LocumJobApplication.STATUS_ACCEPTED,
        ]
        active_locum_qs = LocumJobApplication.objects.filter(
            applicant=user, status__in=active_locum_statuses
        )
        data["active_locum"] = active_locum_qs.count()
        active_locum_week_current, active_locum_week_previous = weekly_counts(
            active_locum_qs, "applied_at"
        )

        # Upcoming Appointments (date >= today and status not cancelled)
        upcoming_appointments_qs = Appointment.objects.filter(
            provider=professional_profile,
            date__gte=today,
        ).exclude(status=Appointment.Status.CANCELLED)
        data["upcoming_appointments"] = upcoming_appointments_qs.count()

        # Appointment Requests (PENDING status)
        appointment_requests_qs = Appointment.objects.filter(
            provider=professional_profile, status=Appointment.Status.PENDING
        )
        data["appointment_requests"] = appointment_requests_qs.count()
        appointment_requests_week_current, appointment_requests_week_previous = (
            weekly_counts(appointment_requests_qs, "created_at")
        )

        # Build metrics progress
        data["metrics_progress"] = [
            build_progress(
                "Total Patients",
                data["total_patients"],
                patients_week_current,
                patients_week_previous,
            ),
            build_progress(
                "Total Prescriptions",
                data["total_prescriptions"],
                prescriptions_week_current,
                prescriptions_week_previous,
            ),
            build_progress(
                "Active Appointments",
                data["active_appointments"],
                active_appointments_week_current,
                active_appointments_week_previous,
            ),
            build_progress(
                "Active Locum Applications",
                data["active_locum"],
                active_locum_week_current,
                active_locum_week_previous,
            ),
            build_progress(
                "Appointment Requests",
                data["appointment_requests"],
                appointment_requests_week_current,
                appointment_requests_week_previous,
            ),
        ]

        # Recent upcoming appointments (next 10)
        recent_upcoming_appointments = upcoming_appointments_qs.order_by(
            "date", "start_time"
        )[:3]
        data["recent_upcoming_appointments"] = AppointmentSerializer(
            instance=recent_upcoming_appointments,
            many=True,
            context={"request": request},
        ).data

        # Recent appointment requests (latest 10)
        recent_appointment_requests = appointment_requests_qs.order_by("-created_at")[
            :3
        ]
        data["recent_appointment_requests"] = AppointmentSerializer(
            instance=recent_appointment_requests,
            many=True,
            context={"request": request},
        ).data

        # patient overview
        # mon - sun for this current week
        current_week_monday = current_week_start.date()
        patient_overview = []
        for i in range(7):  # Monday (0) through Sunday (6)
            day_date = current_week_monday + timedelta(days=i)
            patient_overview.append(
                {
                    "day": day_date.strftime("%A"),
                    "data": {
                        "new_patients": patients_qs.filter(
                            created_at__date=day_date
                        ).count(),
                        "cancelled_visitations": Visitation.objects.filter(
                            issued_by=professional_profile,
                            date_created__date=day_date,
                            status=Visitation.VisitationStatus.CANCELLED,
                        ).count(),
                        "completed_visits": Visitation.objects.filter(
                            issued_by=professional_profile,
                            date_created__date=day_date,
                            status=Visitation.VisitationStatus.COMPLETED,
                        ).count(),
                    },
                }
            )
        data["patient_overview"] = patient_overview

        return Response(data=data, status=status.HTTP_200_OK)


class EducationHistoryVieset(viewsets.ModelViewSet):
    """
    ViewSet for managing education history
    """

    queryset = EducationHistory.objects.all()
    serializer_class = EducationHistorySerializer
    permission_classes = [ProfessionalProfileRequired]
    http_method_names = ["get", "post", "patch", "delete"]

    def get_queryset(self):
        return EducationHistory.objects.filter(
            professional_profile=self.request.user.professional_profile
        )

    def perform_create(self, serializer):
        serializer.save(professional_profile=self.request.user.professional_profile)

    def perform_update(self, serializer):
        serializer.save(professional_profile=self.request.user.professional_profile)


class HealthProgramInvitationViewset(viewsets.ModelViewSet):
    """
    ViewSet for managing health program invitations
    """

    queryset = HealthProgramInvitation.objects.all()
    serializer_class = HealthProgramInvitationSerializer
    permission_classes = [ProfessionalProfileRequired]
    http_method_names = ["get", "post"]

    def get_queryset(self):
        user = self.request.user
        return self.queryset.filter(
            invited_to=user,
            status__in=[
                HealthProgramInvitation.InvitationStatus.PENDING,
                HealthProgramInvitation.InvitationStatus.ACCEPTED,
            ],
        )

    @action(
        detail=False,
        methods=["get"],
        url_path="programs",
        url_name="programs",
    )
    def programs(self, request, *args, **kwargs):
        """
        Get a health program invitation for the current user
        """
        invite_programs = (
            self.queryset.filter(
                invited_to=request.user,
                status__in=[
                    HealthProgramInvitation.InvitationStatus.PENDING,
                    HealthProgramInvitation.InvitationStatus.ACCEPTED,
                ],
            )
            .values_list(
                "program",
                flat=True,
            )
            .distinct()
        )
        programs = HealthProgram.objects.filter(id__in=invite_programs)
        data = HealthProgramSerializer(
            instance=programs,
            many=True,
            context={"request": request},
        ).data
        return Response(data=data, status=status.HTTP_200_OK)

    @action(
        detail=True,
        methods=["get"],
        url_path="interventions",
        url_name="interventions",
    )
    def interventions(self, request, *args, **kwargs):
        """
        Get a health program invitation for the current user
        """
        intivation = self.get_object()

        # check if the invitation has been accpeted.
        if intivation.status != HealthProgramInvitation.InvitationStatus.ACCEPTED:
            raise exceptions.GeneralException(
                detail="Invitation not accepted",
                response_code=status.HTTP_400_BAD_REQUEST,
                error_code=status.HTTP_400_BAD_REQUEST,
            )

        interventions = intivation.intervention.all()

        data = ProgramInterventionSerializer(
            instance=interventions,
            many=True,
            context={"request": request},
        ).data
        return Response(data=data, status=status.HTTP_200_OK)

    @action(
        detail=True,
        methods=["post"],
        url_path="accept",
        url_name="accept",
    )
    def accept(self, request, *args, **kwargs):
        """
        Accept a health program invitation.
        Updates the invitation status to ACCEPTED and sends email notification to the inviter.
        """
        invitation = self.get_object()

        # Check if the invitation belongs to the current user
        if invitation.invited_to != request.user:
            raise exceptions.GeneralException(
                detail="You do not have permission to accept this invitation.",
                response_code=status.HTTP_403_FORBIDDEN,
                error_code=status.HTTP_403_FORBIDDEN,
            )

        # Check if the invitation is still pending
        if invitation.status != HealthProgramInvitation.InvitationStatus.PENDING:
            raise exceptions.GeneralException(
                detail=f"Invitation has already been {invitation.status.lower()}.",
                response_code=status.HTTP_400_BAD_REQUEST,
                error_code=status.HTTP_400_BAD_REQUEST,
            )

        # Check if invitation has expired
        if invitation.expires_at and invitation.expires_at < timezone.now():
            invitation.status = HealthProgramInvitation.InvitationStatus.EXPIRED
            invitation.save()
            raise exceptions.GeneralException(
                detail="This invitation has expired.",
                response_code=status.HTTP_400_BAD_REQUEST,
                error_code=status.HTTP_400_BAD_REQUEST,
            )

        # Update invitation status
        invitation.status = HealthProgramInvitation.InvitationStatus.ACCEPTED
        invitation.save()

        # Send email notification to the inviter
        if invitation.invited_by_user and invitation.invited_by_user.email:
            inviter_name = (
                invitation.invited_by_user.get_full_name()
                or invitation.invited_by_user.email
            )
            # Get professional name - try full name first, then email
            professional_name = request.user.get_full_name() or request.user.email
            program_name = invitation.program.program_name

            generic_send_mail.delay(
                recipient=invitation.invited_by_user.email,
                title=f"Invitation Accepted - {program_name}",
                payload={
                    "user_name": inviter_name,
                    "body": (
                        f"<p>Good news! Your invitation has been accepted.</p>"
                        f"<p><strong>Health Professional:</strong> {professional_name}</p>"
                        f"<p><strong>Program:</strong> {program_name}</p>"
                        f"<p>The health professional <strong>{professional_name}</strong> is now part of your program and can start participating in the interventions.</p>"
                    ),
                },
            )

        serializer = HealthProgramInvitationSerializer(invitation)
        return Response(
            {
                "message": "Invitation accepted successfully.",
                "invitation": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="reject",
        url_name="reject",
    )
    def reject(self, request, *args, **kwargs):
        """
        Reject a health program invitation.
        Updates the invitation status to REJECTED and sends email notification to the inviter.
        """
        invitation = self.get_object()

        # Check if the invitation belongs to the current user
        if invitation.invited_to != request.user:
            raise exceptions.GeneralException(
                detail="You do not have permission to reject this invitation.",
                response_code=status.HTTP_403_FORBIDDEN,
                error_code=status.HTTP_403_FORBIDDEN,
            )

        # Check if the invitation is still pending
        if invitation.status != HealthProgramInvitation.InvitationStatus.PENDING:
            raise exceptions.GeneralException(
                detail=f"Invitation has already been {invitation.status.lower()}.",
                response_code=status.HTTP_400_BAD_REQUEST,
                error_code=status.HTTP_400_BAD_REQUEST,
            )

        # Check if invitation has expired
        if invitation.expires_at and invitation.expires_at < timezone.now():
            invitation.status = HealthProgramInvitation.InvitationStatus.EXPIRED
            invitation.save()
            raise exceptions.GeneralException(
                detail="This invitation has expired.",
                response_code=status.HTTP_400_BAD_REQUEST,
                error_code=status.HTTP_400_BAD_REQUEST,
            )

        # Update invitation status
        invitation.status = HealthProgramInvitation.InvitationStatus.REJECTED
        invitation.save()

        # Send email notification to the inviter
        if invitation.invited_by_user and invitation.invited_by_user.email:
            inviter_name = (
                invitation.invited_by_user.get_full_name()
                or invitation.invited_by_user.email
            )
            # Get professional name - try full name first, then email
            professional_name = request.user.get_full_name() or request.user.email
            program_name = invitation.program.program_name

            generic_send_mail.delay(
                recipient=invitation.invited_by_user.email,
                title=f"Invitation Declined - {program_name}",
                payload={
                    "user_name": inviter_name,
                    "body": (
                        f"<p>We wanted to let you know that your invitation has been declined.</p>"
                        f"<p><strong>Health Professional:</strong> {professional_name}</p>"
                        f"<p><strong>Program:</strong> {program_name}</p>"
                        f"<p>The health professional <strong>{professional_name}</strong> has declined your invitation to participate in the health program <strong>{program_name}</strong>.</p>"
                        f"<p>You may want to consider inviting another health professional for this program.</p>"
                    ),
                },
            )

        serializer = HealthProgramInvitationSerializer(invitation)
        return Response(
            {
                "message": "Invitation rejected successfully.",
                "invitation": serializer.data,
            },
            status=status.HTTP_200_OK,
        )
