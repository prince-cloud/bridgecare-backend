from django.db import models
from django.utils.text import slugify
from accounts.models import CustomUser
from phonenumber_field.modelfields import PhoneNumberField
import uuid


class PartnerProfile(models.Model):
    class OrganizationType(models.TextChoices):
        NGO = "ngo", "NGO"
        GOVERNMENT = "government", "Government"
        CORPORATE = "corporate", "Corporate"
        RESEARCH = "research", "Research Institution"
        FOUNDATION = "foundation", "Foundation"
        INTERNATIONAL = "international", "International Organisation"
        OTHER = "other", "Other"

    class PartnershipType(models.TextChoices):
        FUNDING = "funding", "Funding"
        TECHNICAL = "technical", "Technical"
        SERVICE_PROVIDER = "service_provider", "Service Provider"
        RESEARCH = "research", "Research"
        ADVOCACY = "advocacy", "Advocacy"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        CustomUser, on_delete=models.CASCADE, related_name="partner_profile"
    )
    slug = models.SlugField(max_length=220, unique=True, blank=True)

    # Organization details
    organization_name = models.CharField(max_length=200)
    organization_type = models.CharField(
        max_length=50, choices=OrganizationType.choices, default=OrganizationType.NGO
    )
    organization_size = models.CharField(max_length=50, blank=True, null=True)
    registration_number = models.CharField(max_length=100, blank=True, null=True)
    logo = models.ImageField(upload_to="partner_logos/", blank=True, null=True)

    # Contact information
    organization_phone = PhoneNumberField(blank=True, null=True)
    organization_email = models.EmailField(blank=True, null=True)
    organization_address = models.TextField(blank=True, null=True)
    region = models.CharField(max_length=100, blank=True, null=True)
    district = models.CharField(max_length=100, blank=True, null=True)
    website = models.URLField(blank=True, null=True)

    # Partnership details
    partnership_type = models.CharField(
        max_length=50, choices=PartnershipType.choices, default=PartnershipType.FUNDING
    )
    partnership_status = models.CharField(max_length=50, default="active")
    partnership_start_date = models.DateField(blank=True, null=True)
    partnership_end_date = models.DateField(blank=True, null=True)

    # Access flags (set by admin)
    is_verified = models.BooleanField(default=False)
    can_access_analytics = models.BooleanField(default=True)
    can_manage_subsidies = models.BooleanField(default=True)
    can_view_patient_data = models.BooleanField(default=False)

    # Contact person
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
        return f"{self.organization_name} ({self.user.email})"

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.organization_name)
            slug = base
            n = 1
            while PartnerProfile.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{n}"
                n += 1
            self.slug = slug
        super().save(*args, **kwargs)


class Subsidy(models.Model):
    class SubsidyType(models.TextChoices):
        CASH_GRANT = "cash_grant", "Cash Grant"
        FREE_CONSULTATION = "free_consultation", "Free Consultation"
        MEDICATION_DISCOUNT = "medication_discount", "Medication Discount"
        PROGRAM_FUNDING = "program_funding", "Program Funding"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        PAUSED = "paused", "Paused"
        EXHAUSTED = "exhausted", "Exhausted"
        EXPIRED = "expired", "Expired"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    partner = models.ForeignKey(
        PartnerProfile, on_delete=models.CASCADE, related_name="subsidies"
    )
    name = models.CharField(max_length=200)
    subsidy_type = models.CharField(
        max_length=50, choices=SubsidyType.choices, default=SubsidyType.FREE_CONSULTATION
    )
    total_budget = models.DecimalField(max_digits=14, decimal_places=2)
    budget_used = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    target = models.TextField(help_text="Who this subsidy targets, e.g. 'Rural patients in Tamale'")
    start_date = models.DateField()
    end_date = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "partner_subsidies"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} — {self.partner.organization_name}"

    @property
    def budget_remaining(self):
        return self.total_budget - self.budget_used

    @property
    def utilization_pct(self):
        if self.total_budget:
            return round(float(self.budget_used) / float(self.total_budget) * 100, 1)
        return 0


class ProgramPartnershipRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    class ReportFrequency(models.TextChoices):
        DAILY = "daily", "Daily"
        WEEKLY = "weekly", "Weekly"
        BIWEEKLY = "biweekly", "Bi-weekly"
        MONTHLY = "monthly", "Monthly"
        QUARTERLY = "quarterly", "Quarterly"

    class Direction(models.TextChoices):
        PARTNER_INITIATED = "partner_initiated", "Partner Initiated"
        ORG_INITIATED = "org_initiated", "Organisation Initiated"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    partner = models.ForeignKey(
        PartnerProfile, on_delete=models.CASCADE, related_name="partnership_requests"
    )
    program = models.ForeignKey(
        "communities.HealthProgram",
        on_delete=models.CASCADE,
        related_name="partner_requests",
    )
    direction = models.CharField(
        max_length=30, choices=Direction.choices, default=Direction.PARTNER_INITIATED
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    message = models.TextField(blank=True, help_text="Why the partner wants to monitor this program")
    report_frequency = models.CharField(
        max_length=20, choices=ReportFrequency.choices, default=ReportFrequency.MONTHLY
    )
    contact = models.CharField(max_length=200, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    # Review fields (set by the approving party)
    reviewed_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="reviewed_partner_requests",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "program_partnership_requests"
        ordering = ["-created_at"]
        unique_together = [("partner", "program")]

    def __str__(self):
        arrow = "→" if self.direction == self.Direction.PARTNER_INITIATED else "←"
        return f"{self.partner.organization_name} {arrow} {self.program.program_name} [{self.status}]"


class ProgramMonitor(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    partner = models.ForeignKey(
        PartnerProfile, on_delete=models.CASCADE, related_name="program_monitors"
    )
    program = models.ForeignKey(
        "communities.HealthProgram",
        on_delete=models.CASCADE,
        related_name="partner_monitors",
    )
    request = models.OneToOneField(
        ProgramPartnershipRequest,
        on_delete=models.CASCADE,
        related_name="monitor",
        null=True,
        blank=True,
    )
    report_frequency = models.CharField(
        max_length=20,
        choices=ProgramPartnershipRequest.ReportFrequency.choices,
        default=ProgramPartnershipRequest.ReportFrequency.MONTHLY,
    )
    contact = models.CharField(max_length=200, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "program_monitors"
        ordering = ["-created_at"]
        unique_together = [("partner", "program")]

    def __str__(self):
        return f"{self.partner.organization_name} monitors {self.program.program_name}"
