from django.db import models
from accounts.models import CustomUser
from phonenumber_field.modelfields import PhoneNumberField
import uuid


class PatientProfile(models.Model):
    """
    Specific profile for Patient/User platform users
    """

    class Gender(models.TextChoices):
        MALE = "M"
        FEMALE = "F"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="patient_profile",
        blank=True,
        null=True,
    )
    # basic profile information
    first_name = models.CharField(max_length=100, blank=True, null=True)
    surname = models.CharField(max_length=100, blank=True, null=True)
    other_names = models.CharField(max_length=100, blank=True, null=True)
    last_name = models.CharField(max_length=100, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    phone_number = PhoneNumberField(blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    gender = models.CharField(
        max_length=10,
        choices=Gender.choices,
        blank=True,
        null=True,
    )
    address = models.TextField(blank=True, null=True)

    # media
    profile_picture = models.ImageField(
        upload_to="patients/profile_pictures/",
        blank=True,
        null=True,
    )

    # Basic health information
    blood_type = models.CharField(max_length=5, blank=True, null=True)
    height = models.DecimalField(
        max_digits=5, decimal_places=2, blank=True, null=True
    )  # in cm
    weight = models.DecimalField(
        max_digits=5, decimal_places=2, blank=True, null=True
    )  # in kg

    # Emergency contact
    emergency_contact_name = models.CharField(max_length=200, blank=True, null=True)
    emergency_contact_phone = PhoneNumberField(blank=True, null=True)
    emergency_contact_relationship = models.CharField(
        max_length=100, blank=True, null=True
    )

    # Insurance and payment
    insurance_provider = models.CharField(max_length=100, blank=True, null=True)
    insurance_number = models.CharField(max_length=100, blank=True, null=True)

    # important date
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "patient_profiles"
        verbose_name = "Patient Profile"
        verbose_name_plural = "Patient Profiles"

    def __str__(self):
        return f"{self.user.email}"

    @property
    def bmi(self):
        """Calculate BMI if height and weight are available"""
        if self.height and self.weight:
            height_m = float(self.height) / 100  # Convert cm to m
            weight_kg = float(self.weight)
            return round(weight_kg / (height_m**2), 2)
        return None


# Patient medical records
# class PatientMedicalRecord(models.Model):
