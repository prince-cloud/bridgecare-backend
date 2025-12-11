from django.db import models
from django.utils import timezone
from accounts.models import CustomUser
import uuid

from patients.models import PatientProfile


class Profession(models.Model):
    """
    Profession model
    """

    name = models.CharField(max_length=100)
    description = models.TextField()
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "professions"
        verbose_name = "Profession"
        verbose_name_plural = "Professions"

    def __str__(self):
        return self.name


class Specialization(models.Model):
    """
    Specialization model
    """

    name = models.CharField(max_length=100)
    description = models.TextField()
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "specializations"
        verbose_name = "Specialization"
        verbose_name_plural = "Specializations"

    def __str__(self):
        return self.name


class LicenceIssueAuthority(models.Model):
    """
    Licence issue authority model
    """

    name = models.CharField(max_length=100)
    description = models.TextField()
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "licence_issue_authorities"
        verbose_name = "Licence Issue Authority"
        verbose_name_plural = "Licence Issue Authorities"

    def __str__(self):
        return self.name


class ProfessionalProfile(models.Model):
    """
    Specific profile for Individual Professionals
    """

    class EducationStatus(models.TextChoices):
        IN_SCHOOL = "IN_SCHOOL", "In School"
        COMPLETED = "COMPLETED", "Completed"
        PRACTICING = "PRACTICING", "Practicing"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="professional_profile",
    )

    # profession details
    profession = models.ForeignKey(
        Profession,
        on_delete=models.SET_NULL,
        null=True,
        related_name="professional_profiles",
    )
    specialization = models.ForeignKey(
        Specialization,
        on_delete=models.SET_NULL,
        related_name="professional_profiles",
        blank=True,
        null=True,
    )
    facility_affiliation = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )

    # check weather the person is still in school, completed
    # not in school or practicing
    education_status = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        choices=EducationStatus.choices,
    )

    license_number = models.CharField(max_length=100, null=True, blank=True)
    license_expiry_date = models.DateField(null=True, blank=True)
    license_issuing_authority = models.ForeignKey(
        LicenceIssueAuthority,
        on_delete=models.SET_NULL,
        related_name="professional_profiles",
        blank=True,
        null=True,
    )
    years_of_experience = models.IntegerField(null=True, blank=False)

    is_verified = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "professional_profiles"
        verbose_name = "Professional Profile"
        verbose_name_plural = "Professional Profiles"

    def __str__(self):
        return f"{self.user} - {self.profession}"

    def is_license_valid(self):
        """Check if professional license is valid"""
        if not self.license_expiry_date:
            return False
        return timezone.now().date() <= self.license_expiry_date

    def is_profile_completed(self):
        """Check if profile is completed"""
        if (
            self.education_status
            and self.education_status
            in [
                ProfessionalProfile.EducationStatus.IN_SCHOOL,
                ProfessionalProfile.EducationStatus.COMPLETED,
            ]
            and not self.education_histories.exists()
        ):
            return False
        elif (
            self.education_status == ProfessionalProfile.EducationStatus.PRACTICING
            and not (self.profession and self.license_number)
        ):
            return False
        elif not self.education_histories.exists():
            return False
        else:
            return True


class Availability(models.Model):

    provider = models.OneToOneField(
        ProfessionalProfile,
        on_delete=models.CASCADE,
        related_name="availability",
    )
    patient_visit_availability = models.BooleanField(default=False)
    provider_visit_availability = models.BooleanField(default=False)
    telehealth_availability = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "availabilities"
        verbose_name = "Availability"
        verbose_name_plural = "Availabilities"


class EducationHistory(models.Model):
    """
    Education history model
    """

    class EducationLevel(models.TextChoices):
        DIPLOMA = "DIPLOMA", "Diploma"
        BACHELOR = "BACHELOR", "Bachelor"
        MASTER = "MASTER", "Master"
        DOCTORATE = "DOCTORATE", "Doctorate"
        PROFESSOR = "PROFESSOR", "Professor"
        OTHER = "OTHER", "Other"

    professional_profile = models.ForeignKey(
        ProfessionalProfile,
        on_delete=models.CASCADE,
        related_name="education_histories",
    )
    education_level = models.CharField(
        max_length=100,
        choices=EducationLevel.choices,
        default=EducationLevel.OTHER,
    )
    education_institution = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )
    education_institution_address = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )

    is_current_education = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "education_histories"
        verbose_name = "Education History"
        verbose_name_plural = "Education Histories"

    def __str__(self):
        return f"{self.professional_profile.user.email} - {self.education_level}"


# =============================================================================
# APPOINTMENT BOOKING MODELS
# =============================================================================


class AvailabilityBlock(models.Model):
    """
    Defines a health professional's working schedule for a specific day of the week.
    Supports multiple blocks per day with custom start/end times and slot duration.
    """

    class DayOfWeek(models.IntegerChoices):
        MONDAY = 0, "Monday"
        TUESDAY = 1, "Tuesday"
        WEDNESDAY = 2, "Wednesday"
        THURSDAY = 3, "Thursday"
        FRIDAY = 4, "Friday"
        SATURDAY = 5, "Saturday"
        SUNDAY = 6, "Sunday"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider = models.ForeignKey(
        ProfessionalProfile,
        on_delete=models.CASCADE,
        related_name="availability_blocks",
    )
    day_of_week = models.IntegerField(choices=DayOfWeek.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()
    slot_duration = models.PositiveIntegerField(
        help_text="Duration of each appointment slot in minutes",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "availability_blocks"
        verbose_name = "Availability Block"
        verbose_name_plural = "Availability Blocks"
        ordering = ["provider", "day_of_week", "start_time"]

    def __str__(self):
        day_name = self.DayOfWeek(self.day_of_week).label
        user = self.provider.user
        provider_name = (
            f"{user.first_name} {user.last_name}".strip()
            if (user.first_name or user.last_name)
            else user.email
        )
        return f"{provider_name} - {day_name} {self.start_time}-{self.end_time}"


class BreakPeriod(models.Model):
    """
    Represents a break period inside an availability block.
    Supports multiple breaks inside a block.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    availability = models.ForeignKey(
        AvailabilityBlock, on_delete=models.CASCADE, related_name="break_periods"
    )
    break_start = models.TimeField()
    break_end = models.TimeField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "break_periods"
        verbose_name = "Break Period"
        verbose_name_plural = "Break Periods"
        ordering = ["break_start"]

    def __str__(self):
        return f"{self.availability} - Break {self.break_start}-{self.break_end}"


class Appointment(models.Model):
    """
    Represents a booked time slot.
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        CONFIRMED = "CONFIRMED", "Confirmed"
        CANCELLED = "CANCELLED", "Cancelled"
        COMPLETED = "COMPLETED", "Completed"
        NO_SHOW = "NO_SHOW", "No Show"
        RESCHEDULED = "RESCHEDULED", "Rescheduled"
        MISSED = "MISSED", "Missed"

    class AppointmentType(models.TextChoices):
        TELEHEALTH = "TELEHEALTH", "Telehealth"
        IN_PERSON = "IN_PERSON", "In Person"

    class TelehealthMode(models.TextChoices):
        VIDEO = "VIDEO", "Video"
        CALL = "CALL", "Call"

    class VisitationType(models.TextChoices):
        PATIENT_VISITS_DOCTOR = "PATIENT_VISITS_DOCTOR", "Patient Visits Doctor"
        PROVIDER_VISITS_PATIENT = "PROVIDER_VISITS_PATIENT", "Provider Visits Patient"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(
        PatientProfile,
        on_delete=models.CASCADE,
        related_name="appointments",
    )
    provider = models.ForeignKey(
        ProfessionalProfile,
        on_delete=models.CASCADE,
        related_name="appointments",
    )
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()

    appointment_type = models.CharField(
        choices=AppointmentType.choices,
        max_length=50,
        null=True,
        blank=True,
        help_text="Type of appointment: Telehealth or In Person",
    )
    telehealth_mode = models.CharField(
        choices=TelehealthMode.choices,
        max_length=50,
        null=True,
        blank=True,
        help_text="Mode for telehealth appointments: Online, Video, or Call",
    )
    visitation_type = models.CharField(
        choices=VisitationType.choices,
        max_length=50,
        null=True,
        blank=True,
        help_text="Location for in-person appointments: Patient visits doctor or doctor visits patient",
    )
    visitation_location = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="Location for in-person appointments: Patient visits doctor or doctor visits patient",
    )

    reason = models.TextField(null=True, blank=True)

    status = models.CharField(
        choices=Status.choices,
        default=Status.PENDING,
        max_length=100,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "appointments"
        verbose_name = "Appointment"
        verbose_name_plural = "Appointments"
        ordering = ["date", "start_time"]
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "date", "start_time"],
                name="unique_provider_date_start_time",
            )
        ]

    def __str__(self):
        provider_user = self.provider.user
        provider_name = (
            f"{provider_user.first_name} {provider_user.last_name}".strip()
            if (provider_user.first_name or provider_user.last_name)
            else provider_user.email
        )

        patient_user = self.patient.user if self.patient.user else None
        patient_name = (
            f"{patient_user.first_name} {patient_user.last_name}".strip()
            if patient_user and (patient_user.first_name or patient_user.last_name)
            else (self.patient.email or str(self.patient))
        )

        return f"{patient_name} - {provider_name} on {self.date} at {self.start_time}"
