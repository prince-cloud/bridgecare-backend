from django.db import models
from accounts.models import CustomUser
from phonenumber_field.modelfields import PhoneNumberField


class PatientProfile(models.Model):
    """
    Specific profile for Patient/User platform users
    """

    user = models.OneToOneField(
        CustomUser, on_delete=models.CASCADE, related_name="patient_profile"
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
    preferred_payment_method = models.CharField(max_length=50, default="mobile_money")

    # Preferences
    preferred_language = models.CharField(max_length=10, default="en")
    preferred_consultation_type = models.CharField(max_length=50, default="in_person")
    notification_preferences = models.JSONField(default=dict, blank=True)

    # Health history
    medical_history = models.JSONField(default=list, blank=True)
    allergies = models.JSONField(default=list, blank=True)
    current_medications = models.JSONField(default=list, blank=True)

    # Location
    home_address = models.TextField(blank=True, null=True)
    work_address = models.TextField(blank=True, null=True)
    preferred_pharmacy = models.ForeignKey(
        "pharmacies.PharmacyProfile", on_delete=models.SET_NULL, blank=True, null=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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
