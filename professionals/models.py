from django.db import models
from django.utils import timezone
from accounts.models import CustomUser
from phonenumber_field.modelfields import PhoneNumberField
import uuid


class ProfessionalProfile(models.Model):
    """
    Specific profile for Individual Professionals
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        CustomUser, on_delete=models.CASCADE, related_name="professional_profile"
    )

    # Professional details
    practice_type = models.CharField(max_length=100)  # Private, Public, Locum, etc.
    years_of_experience = models.IntegerField(default=0)
    education_background = models.JSONField(default=list, blank=True)

    # License and certification
    license_number = models.CharField(
        max_length=100, unique=True, blank=True, null=True
    )
    license_issuing_body = models.CharField(max_length=100, blank=True, null=True)
    license_expiry_date = models.DateField(blank=True, null=True)
    certifications = models.JSONField(default=list, blank=True)

    # Availability and preferences
    availability_schedule = models.JSONField(default=dict, blank=True)
    preferred_working_hours = models.JSONField(default=dict, blank=True)
    travel_radius = models.IntegerField(default=0)  # in kilometers

    # Financial information
    hourly_rate = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True
    )
    currency = models.CharField(max_length=3, default="GHS")

    # Specializations and skills
    specializations = models.JSONField(default=list, blank=True)
    languages_spoken = models.JSONField(default=list, blank=True)

    # References
    emergency_contact = models.CharField(max_length=200, blank=True, null=True)
    emergency_phone = PhoneNumberField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "professional_profiles"
        verbose_name = "Professional Profile"
        verbose_name_plural = "Professional Profiles"

    def __str__(self):
        return f"{self.user.email} - {self.user.primary_role}"

    def is_license_valid(self):
        """Check if professional license is valid"""
        if not self.license_expiry_date:
            return False
        return timezone.now().date() <= self.license_expiry_date
