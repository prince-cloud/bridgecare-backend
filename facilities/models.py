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
    facility_type = models.CharField(max_length=100)  # Hospital, Clinic, CHPS, etc.
    address = models.TextField()
    district = models.CharField(max_length=100)
    region = models.CharField(max_length=100)
    phone_number = PhoneNumberField(blank=True, null=True)
    email = models.EmailField(blank=True, null=True)

    # Location

    latitude = models.CharField(max_length=50, null=True, blank=True)
    longitude = models.CharField(max_length=50, null=True, blank=True)

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
