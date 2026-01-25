from django.db import models
from accounts.models import CustomUser
from phonenumber_field.modelfields import PhoneNumberField
import uuid


class PharmacyProfile(models.Model):
    """
    Specific profile for Pharmacy platform users
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="pharmacy_profile",
    )

    # Pharmacy details
    pharmacy_name = models.CharField(max_length=200)
    pharmacy_license = models.CharField(max_length=100, unique=True)

    # Location
    address = models.TextField()
    district = models.CharField(max_length=100, null=True, blank=True)
    region = models.CharField(max_length=100, null=True, blank=True)
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        blank=True,
        null=True,
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        blank=True,
        null=True,
    )

    # Contact information
    phone_number = PhoneNumberField()
    email = models.EmailField(blank=True, null=True)
    website = models.URLField(blank=True, null=True)

    # Services and capabilities
    delivery_available = models.BooleanField(default=False)
    delivery_radius = models.IntegerField(default=0)

    # Staff information
    pharmacist_license = models.CharField(max_length=100, blank=True, null=True)
    license_expiry_date = models.DateField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pharmacy_profiles"
        verbose_name = "Pharmacy Profile"
        verbose_name_plural = "Pharmacy Profiles"

    def __str__(self):
        return f"{self.user.email} - {self.pharmacy_name}"
