from rest_framework import serializers
from .models import (
    ProfessionalProfile,
    Profession,
    Specialization,
    LicenceIssueAuthority,
    Availability,
    AvailabilityBlock,
    BreakPeriod,
    Appointment,
)
from accounts.serializers import UserSerializer
from helpers import exceptions


class ProfessionsSerializer(serializers.ModelSerializer):
    """
    Professions serializer
    """

    class Meta:
        model = Profession
        fields = (
            "id",
            "name",
            "description",
        )


class SpecializationSerializer(serializers.ModelSerializer):
    """
    Specialization serializer
    """

    class Meta:
        model = Specialization
        fields = (
            "id",
            "name",
            "description",
        )


class LicenceIssueAuthoritySerializer(serializers.ModelSerializer):
    """
    Licence issue authority serializer
    """

    class Meta:
        model = LicenceIssueAuthority
        fields = (
            "id",
            "name",
            "description",
        )


class ProfessionalProfileSerializer(serializers.ModelSerializer):
    """
    Professional profile serializer
    """

    user = UserSerializer(read_only=True)

    availability = serializers.SerializerMethodField()

    def get_availability(self, obj):
        if hasattr(obj, "availability"):
            return {
                "patient_visit_availability": obj.availability.patient_visit_availability,
                "provider_visit_availability": obj.availability.provider_visit_availability,
                "telehealth_availability": obj.availability.telehealth_availability,
            }
        return {
            "patient_visit_availability": False,
            "provider_visit_availability": False,
            "telehealth_availability": False,
        }

    class Meta:
        model = ProfessionalProfile
        fields = (
            "id",
            "user",
            "availability",
            "education_status",
            "profession",
            "specialization",
            "facility_affiliation",
            "license_number",
            "license_expiry_date",
            "license_issuing_authority",
            "years_of_experience",
            "is_active",
            "is_profile_completed",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


# =============================================================================
# AVAILABILITY SERIALIZERS
# =============================================================================


class AvailabilitySerializer(serializers.ModelSerializer):
    """Serializer for provider availability preferences"""

    class Meta:
        model = Availability
        fields = (
            "id",
            "provider",
            "patient_visit_availability",
            "provider_visit_availability",
            "telehealth_availability",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "provider", "created_at", "updated_at")


# =============================================================================
# APPOINTMENT SERIALIZERS
# =============================================================================


class AvailabilityBlockSerializer(serializers.ModelSerializer):
    """Serializer for availability blocks"""

    day_name = serializers.CharField(source="get_day_of_week_display", read_only=True)

    class Meta:
        model = AvailabilityBlock
        fields = (
            "id",
            "provider",
            "day_of_week",
            "day_name",
            "start_time",
            "end_time",
            "slot_duration",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate(self, attrs):
        """Validate availability block"""
        start_time = attrs.get("start_time")
        end_time = attrs.get("end_time")
        slot_duration = attrs.get("slot_duration")

        if start_time and end_time:
            if start_time >= end_time:
                raise exceptions.GeneralException("Start time must be before end time.")

        if slot_duration and slot_duration <= 0:
            raise exceptions.GeneralException("Slot duration must be greater than 0.")

        # Check for overlapping blocks for the same provider and day
        provider = attrs.get("provider")
        day_of_week = attrs.get("day_of_week")
        instance_id = self.instance.id if self.instance else None

        if provider and day_of_week and start_time and end_time:
            overlapping_blocks = AvailabilityBlock.objects.filter(
                provider=provider,
                day_of_week=day_of_week,
            ).exclude(id=instance_id)

            for block in overlapping_blocks:
                if not (end_time <= block.start_time or start_time >= block.end_time):
                    raise exceptions.GeneralException(
                        f"This availability block overlaps with an existing block on {AvailabilityBlock.DayOfWeek(day_of_week).label} ({block.start_time}-{block.end_time})."
                    )

        return attrs


class BreakPeriodSerializer(serializers.ModelSerializer):
    """Serializer for break periods"""

    class Meta:
        model = BreakPeriod
        fields = (
            "id",
            "availability",
            "break_start",
            "break_end",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate(self, attrs):
        """Validate break period"""
        break_start = attrs.get("break_start")
        break_end = attrs.get("break_end")
        availability = attrs.get("availability") or (
            self.instance.availability if self.instance else None
        )

        if break_start and break_end:
            if break_start >= break_end:
                raise exceptions.GeneralException(
                    "Break start time must be before break end time."
                )

        # Validate break is within availability block
        if availability and break_start and break_end:
            if (
                break_start < availability.start_time
                or break_end > availability.end_time
            ):
                raise exceptions.GeneralException(
                    f"Break period must be within the availability block ({availability.start_time}-{availability.end_time})."
                )

            # Check for overlapping breaks in the same availability block
            instance_id = self.instance.id if self.instance else None
            overlapping_breaks = BreakPeriod.objects.filter(
                availability=availability,
            ).exclude(id=instance_id)

            for break_period in overlapping_breaks:
                if not (
                    break_end <= break_period.break_start
                    or break_start >= break_period.break_end
                ):
                    raise exceptions.GeneralException(
                        f"This break period overlaps with an existing break ({break_period.break_start}-{break_period.break_end})."
                    )

        return attrs


class AppointmentSerializer(serializers.ModelSerializer):
    """Serializer for appointments"""

    provider_name = serializers.SerializerMethodField()

    class Meta:
        model = Appointment
        fields = (
            "id",
            "patient",
            "provider",
            "provider_name",
            "date",
            "start_time",
            "end_time",
            "appointment_type",
            "telehealth_mode",
            "visitation_type",
            "visitation_location",
            "reason",
            "status",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "end_time",
            "status",
            "created_at",
            "updated_at",
        )

    def get_provider_name(self, obj):
        """Get provider's name"""
        user = obj.provider.user
        name = f"{user.first_name} {user.last_name}".strip()
        return name if name else user.email


class AppointmentCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating appointments"""

    class Meta:
        model = Appointment
        fields = (
            "provider",
            "date",
            "start_time",
            "appointment_type",
            "telehealth_mode",
            "visitation_type",
            "visitation_location",
            "reason",
        )

    def validate(self, attrs):
        """Validate appointment can be booked"""
        provider = attrs.get("provider")
        appointment_date = attrs.get("date")
        start_time = attrs.get("start_time")

        if not provider or not appointment_date or not start_time:
            raise exceptions.GeneralException(
                "Provider, date, and start_time are required."
            )

        # Get day of week
        day_of_week = appointment_date.weekday()

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
            if block.start_time <= start_time < block.end_time:
                # Check if there's enough time in the block for the slot
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
            if break_period.break_start <= start_time < break_period.break_end:
                raise exceptions.GeneralException(
                    "Start time conflicts with provider's break period."
                )

        # Calculate end_time
        from datetime import datetime, timedelta

        start_datetime = datetime.combine(appointment_date, start_time)
        end_datetime = start_datetime + timedelta(minutes=slot_duration)
        end_time = end_datetime.time()

        # Check if end_time conflicts with breaks
        for break_period in breaks:
            if (
                start_time < break_period.break_end
                and end_time > break_period.break_start
            ):
                raise exceptions.GeneralException(
                    "Appointment time conflicts with provider's break period."
                )

        # Check if slot is already booked
        conflicting_appointments = (
            Appointment.objects.filter(
                provider=provider,
                date=appointment_date,
            )
            .exclude(start_time__gte=end_time)
            .exclude(end_time__lte=start_time)
        )

        if conflicting_appointments.exists():
            raise exceptions.GeneralException(
                "This time slot is already booked. Please choose another time."
            )

        # Set end_time in validated_data
        attrs["end_time"] = end_time

        # Validate appointment type and related fields
        appointment_type = attrs.get("appointment_type")
        telehealth_mode = attrs.get("telehealth_mode")
        visitation_location = attrs.get("visitation_location")

        if appointment_type == Appointment.AppointmentType.TELEHEALTH:
            if not telehealth_mode:
                raise exceptions.GeneralException(
                    "telehealth_mode is required when appointment_type is TELEHEALTH."
                )
            # Clear visit_location if telehealth
            if visitation_location:
                attrs["visitation_location"] = None
        elif (
            appointment_type == Appointment.AppointmentType.IN_PERSON
            and appointment_type == Appointment.VisitationType.PROVIDER_VISITS_PATIENT
        ):
            if not visitation_location:
                raise serializers.ValidationError(
                    "visit_location is required when appointment_type is IN_PERSON."
                )
            # Clear telehealth_mode if in person
            if telehealth_mode:
                attrs["telehealth_mode"] = None
        elif appointment_type is None:
            # Allow appointment_type to be optional for backward compatibility
            # Clear both related fields if appointment_type is not set
            if telehealth_mode:
                attrs["telehealth_mode"] = None
            if visitation_location:
                attrs["visitation_location"] = None

        return attrs


class AvailableTimeSlotSerializer(serializers.Serializer):
    """Serializer for available time slots"""

    time = serializers.TimeField()
    is_available = serializers.BooleanField()
    slot_duration = serializers.IntegerField()


class AvailableTimeSlotsQuerySerializer(serializers.Serializer):
    """Serializer for available time slots query parameters"""

    provider_id = serializers.UUIDField(
        required=True, help_text="The professional profile ID"
    )
    date = serializers.DateField(
        required=True,
        help_text="The date to check availability (format: YYYY-MM-DD)",
        input_formats=["%Y-%m-%d"],
    )


class AvailableTimeSlotsResponseSerializer(serializers.Serializer):
    """Serializer for available time slots response"""

    provider_id = serializers.UUIDField()
    provider_name = serializers.CharField()
    date = serializers.DateField()
    time_slots = AvailableTimeSlotSerializer(many=True)


class AppointmentStatusChangeSerializer(serializers.Serializer):
    """Serializer for changing appointment status"""

    status = serializers.ChoiceField(
        choices=[
            (Appointment.Status.COMPLETED, Appointment.Status.COMPLETED.label),
            (Appointment.Status.NO_SHOW, Appointment.Status.NO_SHOW.label),
            (Appointment.Status.CANCELLED, Appointment.Status.CANCELLED.label),
        ],
        help_text="New status: COMPLETED, NO_SHOW, or CANCELLED",
    )
    comment = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Comment/message to include in notification to patient",
    )

    def validate_status(self, value):
        """Validate status change is allowed"""
        return value


class AppointmentRescheduleSerializer(serializers.Serializer):
    """Serializer for rescheduling appointments"""

    date = serializers.DateField(
        required=True, help_text="New appointment date (format: YYYY-MM-DD)"
    )
    start_time = serializers.TimeField(
        required=True, help_text="New appointment start time (format: HH:MM:SS)"
    )
    comment = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Comment/message to include in notification to patient",
    )

    def validate(self, attrs):
        """Validate rescheduling can be done"""
        # This validation will be done in the view where we have access to the appointment instance
        return attrs


class PatientAppointmentActionSerializer(serializers.Serializer):
    """Serializer for patient appointment actions (reschedule or cancel)"""

    action = serializers.ChoiceField(
        choices=[("reschedule", "Reschedule"), ("cancel", "Cancel")],
        help_text="Action to perform: 'reschedule' or 'cancel'",
    )
    date = serializers.DateField(
        required=False,
        help_text="New appointment date for rescheduling (format: YYYY-MM-DD). Required if action is 'reschedule'",
    )
    start_time = serializers.TimeField(
        required=False,
        help_text="New appointment start time for rescheduling (format: HH:MM:SS). Required if action is 'reschedule'",
    )
    comment = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Comment/message to include in notification",
    )

    def validate(self, attrs):
        """Validate that date and start_time are provided when action is reschedule"""
        action = attrs.get("action")
        date = attrs.get("date")
        start_time = attrs.get("start_time")

        if action == "reschedule":
            if not date:
                raise serializers.ValidationError(
                    {"date": "Date is required when action is 'reschedule'."}
                )
            if not start_time:
                raise serializers.ValidationError(
                    {
                        "start_time": "Start time is required when action is 'reschedule'."
                    }
                )

        return attrs
