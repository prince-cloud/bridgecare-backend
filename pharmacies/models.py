from django.db import models
from accounts.models import CustomUser
from phonenumber_field.modelfields import PhoneNumberField


class PharmacyProfile(models.Model):
    """
    Specific profile for Pharmacy platform users
    """

    user = models.OneToOneField(
        CustomUser, on_delete=models.CASCADE, related_name="pharmacy_profile"
    )

    # Pharmacy details
    pharmacy_name = models.CharField(max_length=200)
    pharmacy_license = models.CharField(max_length=100, unique=True)
    pharmacy_type = models.CharField(max_length=100)  # Retail, Hospital, Clinic, etc.

    # Location
    address = models.TextField()
    district = models.CharField(max_length=100)
    region = models.CharField(max_length=100)
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, blank=True, null=True
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, blank=True, null=True
    )

    # Contact information
    phone_number = PhoneNumberField()
    email = models.EmailField(blank=True, null=True)
    website = models.URLField(blank=True, null=True)

    # Services and capabilities
    services_offered = models.JSONField(default=list, blank=True)
    delivery_available = models.BooleanField(default=False)
    delivery_radius = models.IntegerField(default=0)  # in kilometers
    operating_hours = models.JSONField(default=dict, blank=True)

    # Staff information
    pharmacist_license = models.CharField(max_length=100, blank=True, null=True)
    staff_count = models.IntegerField(default=1)

    # Financial
    payment_methods = models.JSONField(default=list, blank=True)
    insurance_accepted = models.JSONField(default=list, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pharmacy_profiles"
        verbose_name = "Pharmacy Profile"
        verbose_name_plural = "Pharmacy Profiles"

    def __str__(self):
        return f"{self.user.email} - {self.pharmacy_name}"
