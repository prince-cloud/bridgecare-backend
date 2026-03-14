from django.db import models
from django.utils.text import slugify
from accounts.models import CustomUser
from phonenumber_field.modelfields import PhoneNumberField
import uuid


class FacilityType(models.TextChoices):
    HOSPITAL = "hospital", "Hospital"
    CLINIC = "clinic", "Clinic"
    CHPS = "chps", "CHPS"
    OTHER = "other", "Other"


class Facility(models.Model):
    """
    Health facilities that users can be affiliated with
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    facility_type = models.CharField(max_length=100)  # Hospital, Clinic, CHPS, etc.
    address = models.TextField()
    district = models.CharField(max_length=100)
    region = models.CharField(max_length=100)
    phone_number = PhoneNumberField(blank=True, null=True)
    email = models.EmailField(blank=True, null=True)

    # Location
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, blank=True, null=True
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, blank=True, null=True
    )

    # slug
    slug = models.SlugField(unique=True, blank=True, null=True)

    # Status
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "facilities"
        verbose_name = "Facility"
        verbose_name_plural = "Facilities"

    def __str__(self):
        return self.name

    # uniquely create slug from name
    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            unique_slug = base_slug
            num = 1
            # Check if slug already exists and make it unique
            while Facility.objects.filter(slug=unique_slug).exists():
                unique_slug = f"{base_slug}-{num}"
                num += 1
            self.slug = unique_slug
        super().save(*args, **kwargs)


class FacilityProfile(models.Model):
    """
    Specific profile for Health Facility users
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        CustomUser, on_delete=models.CASCADE, related_name="facility_profile"
    )
    facility = models.ForeignKey(
        "Facility", on_delete=models.CASCADE, related_name="staff"
    )

    # Employment details
    employee_id = models.CharField(max_length=50, blank=True, null=True)
    department = models.CharField(max_length=100, blank=True, null=True)
    position = models.CharField(max_length=100, blank=True, null=True)
    employment_type = models.CharField(
        max_length=50, blank=True, null=True
    )  # Full-time, Part-time, Contract
    hire_date = models.DateField(blank=True, null=True)

    # Work schedule
    shift_schedule = models.JSONField(default=dict, blank=True)
    working_hours = models.JSONField(default=dict, blank=True)

    # Access and permissions
    can_prescribe = models.BooleanField(default=False)  # For doctors
    can_access_patient_data = models.BooleanField(default=True)
    can_manage_inventory = models.BooleanField(default=False)
    can_schedule_appointments = models.BooleanField(default=False)

    # Supervisor information
    supervisor = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="subordinates",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "facility_profiles"
        verbose_name = "Facility Profile"
        verbose_name_plural = "Facility Profiles"

    def __str__(self):
        return f"{self.user.email} - {self.facility.name}"


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
        Facility,
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
