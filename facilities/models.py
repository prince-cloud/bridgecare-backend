from django.db import models
from django.utils.text import slugify
from accounts.models import CustomUser
from phonenumber_field.modelfields import PhoneNumberField
import uuid


class FacilityType(models.TextChoices):
    HOSPITAL = "hospital", "Hospital"
    CLINIC = "clinic", "Clinic"
    HEALTH_CENTER = "health_center", "Health Center"
    POLYCLINIC = "polyclinic", "Polyclinic"
    DIAGNOSTIC_CENTER = "diagnostic_center", "Diagnostic Center"
    LABORATORY = "laboratory", "Laboratory"
    PHARMACY = "pharmacy", "Pharmacy"
    DENTAL_CLINIC = "dental_clinic", "Dental Clinic"
    MENTAL_HEALTH_CENTER = "mental_health_center", "Mental Health Center"
    NURSING_HOME = "nursing_home", "Nursing Home"
    REHABILITATION_CENTER = "rehabilitation_center", "Rehabilitation Center"
    CHPS = "chps", "CHPS"
    OTHER = "other", "Other"


class FacilityProfile(models.Model):
    """
    Health facilities that users can be affiliated with
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="facility_profile",
    )
    name = models.CharField(max_length=200)
    facility_type = models.CharField(max_length=100)
    address = models.TextField()
    district = models.CharField(max_length=100)
    region = models.CharField(max_length=100)
    phone_number = PhoneNumberField(blank=True, null=True)
    email = models.EmailField(blank=True, null=True)

    # Ghana-specific registration
    ghs_registration_number = models.CharField(max_length=100, blank=True, null=True)
    nhis_accreditation_number = models.CharField(max_length=100, blank=True, null=True)

    # Facility branding
    logo = models.ImageField(upload_to="facilities/logos/", blank=True, null=True)

    # Operating hours — {"monday": {"open": "08:00", "close": "17:00", "closed": false}, ...}
    operating_hours = models.JSONField(blank=True, null=True)

    # Location
    latitude = models.CharField(max_length=50, null=True, blank=True)
    longitude = models.CharField(max_length=50, null=True, blank=True)

    slug = models.SlugField(unique=True, blank=True, null=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "facilities"
        verbose_name = "Facility"
        verbose_name_plural = "Facilities"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            unique_slug = base_slug
            num = 1
            while FacilityProfile.objects.filter(slug=unique_slug).exists():
                unique_slug = f"{base_slug}-{num}"
                num += 1
            self.slug = unique_slug
        super().save(*args, **kwargs)


class Locum(models.Model):
    class Profession(models.TextChoices):
        DOCTOR = "doctor", "Doctor"
        NURSE = "nurse", "Nurse"
        MIDWIFE = "midwife", "Midwife"
        PHARMACIST = "pharmacist", "Pharmacist"
        LAB_TECHNICIAN = "lab_technician", "Lab Technician"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="locum_profile",
    )
    full_name = models.CharField(max_length=200)
    profession = models.CharField(max_length=40, choices=Profession.choices)
    phone_number = PhoneNumberField(blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    license_number = models.CharField(max_length=100, blank=True, null=True)
    years_of_experience = models.PositiveIntegerField(default=0)
    is_available = models.BooleanField(default=True)
    region = models.CharField(max_length=100, blank=True, null=True)
    district = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "locums"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.full_name} ({self.profession})"


class FacilityStaff(models.Model):
    facility = models.ForeignKey(
        FacilityProfile,
        on_delete=models.CASCADE,
        related_name="staff_members",
    )
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="facility_staff",
    )
    full_name = models.CharField(max_length=200)
    profession = models.CharField(max_length=40, choices=Locum.Profession.choices)
    employee_id = models.CharField(max_length=50, blank=True, null=True)
    position = models.CharField(max_length=100, blank=True, null=True)
    department = models.CharField(max_length=100, blank=True, null=True)
    phone_number = PhoneNumberField(blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    hire_date = models.DateField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "facility_staff"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["facility", "is_active"]),
            models.Index(fields=["facility", "profession"]),
        ]

    def __str__(self):
        return f"{self.full_name} - {self.facility.name}"


class Ward(models.Model):
    class WardType(models.TextChoices):
        GENERAL = "general", "General"
        ICU = "icu", "ICU"
        MATERNITY = "maternity", "Maternity"
        PEDIATRIC = "pediatric", "Pediatric"
        SURGICAL = "surgical", "Surgical"
        EMERGENCY = "emergency", "Emergency"
        ISOLATION = "isolation", "Isolation"
        PSYCHIATRIC = "psychiatric", "Psychiatric"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    facility = models.ForeignKey(
        FacilityProfile,
        on_delete=models.CASCADE,
        related_name="wards",
    )
    name = models.CharField(max_length=100)
    ward_type = models.CharField(max_length=50, choices=WardType.choices, default=WardType.GENERAL)
    description = models.TextField(blank=True, null=True)
    capacity = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "facility_wards"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} - {self.facility.name}"

    @property
    def occupied_beds(self):
        return self.beds.filter(status=Bed.BedStatus.OCCUPIED).count()

    @property
    def available_beds(self):
        return self.beds.filter(status=Bed.BedStatus.AVAILABLE).count()


class Bed(models.Model):
    class BedStatus(models.TextChoices):
        AVAILABLE = "available", "Available"
        OCCUPIED = "occupied", "Occupied"
        MAINTENANCE = "maintenance", "Under Maintenance"
        RESERVED = "reserved", "Reserved"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ward = models.ForeignKey(Ward, on_delete=models.CASCADE, related_name="beds")
    bed_number = models.CharField(max_length=20)
    status = models.CharField(max_length=20, choices=BedStatus.choices, default=BedStatus.AVAILABLE)

    # When occupied — who is the patient
    patient = models.ForeignKey(
        "patients.PatientProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bed_assignments",
    )
    admitted_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "facility_beds"
        ordering = ["bed_number"]
        unique_together = [("ward", "bed_number")]

    def __str__(self):
        return f"Bed {self.bed_number} - {self.ward.name}"


class FacilityAppointment(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        CONFIRMED = "CONFIRMED", "Confirmed"
        CANCELLED = "CANCELLED", "Cancelled"
        COMPLETED = "COMPLETED", "Completed"
        NO_SHOW = "NO_SHOW", "No Show"
        RESCHEDULED = "RESCHEDULED", "Rescheduled"

    class AppointmentType(models.TextChoices):
        IN_PERSON = "IN_PERSON", "In Person"
        TELEHEALTH = "TELEHEALTH", "Telehealth"

    class ConsultationType(models.TextChoices):
        GENERAL = "general", "General Consultation"
        FOLLOW_UP = "follow_up", "Follow-Up"
        EMERGENCY = "emergency", "Emergency"
        ANTENATAL = "antenatal", "Antenatal"
        VACCINATION = "vaccination", "Vaccination"
        LAB_TEST = "lab_test", "Lab Test"
        SPECIALIST = "specialist", "Specialist"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    facility = models.ForeignKey(
        FacilityProfile,
        on_delete=models.CASCADE,
        related_name="appointments",
    )
    patient = models.ForeignKey(
        "patients.PatientProfile",
        on_delete=models.CASCADE,
        related_name="facility_appointments",
    )
    provider = models.ForeignKey(
        FacilityStaff,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="appointments",
    )
    appointment_type = models.CharField(
        max_length=20,
        choices=AppointmentType.choices,
        default=AppointmentType.IN_PERSON,
    )
    consultation_type = models.CharField(
        max_length=30,
        choices=ConsultationType.choices,
        default=ConsultationType.GENERAL,
    )
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField(null=True, blank=True)
    reason = models.TextField(null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "facility_appointments"
        ordering = ["date", "start_time"]

    def __str__(self):
        return f"{self.patient.patient_id} - {self.date} {self.start_time}"


class LabTest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SAMPLE_COLLECTED = "sample_collected", "Sample Collected"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    class TestCategory(models.TextChoices):
        HAEMATOLOGY = "haematology", "Haematology"
        BIOCHEMISTRY = "biochemistry", "Biochemistry"
        MICROBIOLOGY = "microbiology", "Microbiology"
        PARASITOLOGY = "parasitology", "Parasitology"
        RADIOLOGY = "radiology", "Radiology"
        IMMUNOLOGY = "immunology", "Immunology"
        HISTOPATHOLOGY = "histopathology", "Histopathology"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    facility = models.ForeignKey(
        FacilityProfile,
        on_delete=models.CASCADE,
        related_name="lab_tests",
    )
    patient = models.ForeignKey(
        "patients.PatientProfile",
        on_delete=models.CASCADE,
        related_name="lab_tests",
    )
    # Link to visitation if issued during a clinical visit
    visitation = models.ForeignKey(
        "patients.Visitation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lab_tests",
    )
    ordered_by = models.ForeignKey(
        FacilityStaff,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ordered_lab_tests",
    )
    test_name = models.CharField(max_length=200)
    test_category = models.CharField(
        max_length=50,
        choices=TestCategory.choices,
        default=TestCategory.OTHER,
    )
    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.PENDING,
    )
    result = models.TextField(blank=True, null=True)
    result_file = models.FileField(upload_to="lab_results/", blank=True, null=True)
    reference_range = models.CharField(max_length=200, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    collected_at = models.DateTimeField(null=True, blank=True)
    resulted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "facility_lab_tests"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.test_name} - {self.patient.patient_id}"


class StaffInvitation(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        EXPIRED = "expired", "Expired"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    facility = models.ForeignKey(
        FacilityProfile,
        on_delete=models.CASCADE,
        related_name="staff_invitations",
    )
    email = models.EmailField()
    full_name = models.CharField(max_length=200)
    profession = models.CharField(max_length=40, choices=Locum.Profession.choices)
    position = models.CharField(max_length=100, blank=True, null=True)
    department = models.CharField(max_length=100, blank=True, null=True)
    token = models.CharField(max_length=64, unique=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "facility_staff_invitations"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.email} - {self.facility.name}"
