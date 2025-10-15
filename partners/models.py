from django.db import models
from accounts.models import CustomUser
from phonenumber_field.modelfields import PhoneNumberField


class PartnerProfile(models.Model):
    """
    Specific profile for Partner platform users
    """

    user = models.OneToOneField(
        CustomUser, on_delete=models.CASCADE, related_name="partner_profile"
    )

    # Organization details
    organization_name = models.CharField(max_length=200)
    organization_type = models.CharField(
        max_length=100
    )  # NGO, Government, Corporate, etc.
    organization_size = models.CharField(max_length=50, blank=True, null=True)

    # Contact information
    organization_phone = PhoneNumberField(blank=True, null=True)
    organization_email = models.EmailField(blank=True, null=True)
    organization_address = models.TextField(blank=True, null=True)
    website = models.URLField(blank=True, null=True)

    # Partnership details
    partnership_type = models.CharField(
        max_length=100
    )  # Funding, Technical, Service Provider
    partnership_status = models.CharField(max_length=50, default="active")
    partnership_start_date = models.DateField(blank=True, null=True)
    partnership_end_date = models.DateField(blank=True, null=True)

    # API and integration access
    api_access_level = models.CharField(max_length=50, default="basic")
    can_access_analytics = models.BooleanField(default=False)
    can_manage_subsidies = models.BooleanField(default=False)
    can_view_patient_data = models.BooleanField(default=False)

    # Contact person details
    contact_person_name = models.CharField(max_length=200, blank=True, null=True)
    contact_person_title = models.CharField(max_length=100, blank=True, null=True)
    contact_person_phone = PhoneNumberField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "partner_profiles"
        verbose_name = "Partner Profile"
        verbose_name_plural = "Partner Profiles"

    def __str__(self):
        return f"{self.user.email} - {self.organization_name}"
