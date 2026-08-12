from django.db import models
from django.utils import timezone
from accounts.models import CustomUser
from phonenumber_field.modelfields import PhoneNumberField
from django.utils.text import slugify
import re
import secrets
import uuid


# =============================================================================
# COMMUNITY PROFILE MODEL
# =============================================================================


class Organization(models.Model):
    """
    Specific profile for Community platform users (NGOs, churches, CBOs, CHPS coordinators)
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.OneToOneField(
        CustomUser, on_delete=models.CASCADE, related_name="community_profile"
    )
    organization_name = models.CharField(max_length=200, blank=True, null=True)
    organization_type = models.CharField(
        max_length=100, blank=True, null=True
    )  # NGO, Church, CBO, etc.

    # Contact information for organization
    organization_phone = PhoneNumberField(blank=True, null=True)
    organization_email = models.EmailField(blank=True, null=True)
    organization_address = models.TextField(blank=True, null=True)
    registration_number = models.CharField(max_length=100, blank=True, null=True)

    # orgnaization profile
    orgnaization_logo = models.ImageField(
        upload_to="orgnaization_logos/", blank=True, null=True
    )
    banner = models.ImageField(upload_to="organization_banners/", blank=True, null=True)
    verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    slug = models.SlugField(unique=True, blank=True, null=True)

    # Short human-readable prefix for participant IDs, e.g. "SJ" for
    # St. Joana Foundation, producing codes like "SJ001". Auto-derived from the
    # organisation's initials on first save and unique platform-wide so codes
    # from different organisations can never collide.
    participant_code_prefix = models.CharField(
        max_length=6,
        unique=True,
        blank=True,
        null=True,
        help_text="Prefix used for participant IDs, e.g. 'SJ' → SJ001.",
    )

    class Meta:
        db_table = "organizations"
        verbose_name = "Organization"
        verbose_name_plural = "Organizations"

    def __str__(self):
        return f"{self.user.email} - {self.organization_name or 'Organization'}"

    def _derive_code_prefix(self) -> str:
        """
        Build a short prefix from the organisation's initials.

        "St. Joana Foundation" → "JF" ("St." is dropped as a stop-word).
        Falls back to the first letters of the name, then to "ORG".
        """
        name = (self.organization_name or "").strip()
        if not name:
            return "ORG"

        skip = {"the", "of", "and", "for", "a", "an", "st"}
        words = [w for w in re.split(r"[^A-Za-z0-9]+", name) if w]
        initials = "".join(w[0] for w in words if w.lower() not in skip).upper()

        if not initials:
            initials = "".join(w[0] for w in words).upper()
        return (initials or "ORG")[:6] or "ORG"

    def ensure_code_prefix(self) -> str:
        """
        Assign a participant-code prefix if this organisation has none.

        Organisations are created by a post_save signal on the user *before*
        the signup wizard supplies a name, so the prefix cannot be derived at
        creation time. It is allocated on the first save that has a name, and
        lazily here for organisations that predate this field.
        """
        if self.participant_code_prefix:
            return self.participant_code_prefix

        self.participant_code_prefix = self._unique_code_prefix()
        Organization.objects.filter(pk=self.pk).update(
            participant_code_prefix=self.participant_code_prefix
        )
        return self.participant_code_prefix

    def _unique_code_prefix(self) -> str:
        """Reserve a prefix nobody else holds."""
        base = self._derive_code_prefix()

        # Prefer the shortest readable form: "SJ" before "SJF".
        candidates = [base[:2], base[:3], base]
        seen = set()
        for candidate in candidates:
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            if not Organization.objects.filter(
                participant_code_prefix=candidate
            ).exclude(pk=self.pk).exists():
                return candidate

        # Everything readable is taken; append a counter.
        num = 2
        while True:
            candidate = f"{base[:4]}{num}"
            if not Organization.objects.filter(
                participant_code_prefix=candidate
            ).exclude(pk=self.pk).exists():
                return candidate
            num += 1

    # uniquely create slug from name
    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.organization_name)
            unique_slug = base_slug
            num = 1
            # Check if slug already exists and make it unique
            while Organization.objects.filter(slug=unique_slug).exists():
                unique_slug = f"{base_slug}-{num}"
                num += 1
            self.slug = unique_slug

        # Only once a name exists — the profile is created by a signal before
        # the signup wizard has supplied one, and "ORG" would be a poor prefix
        # to lock in permanently.
        if not self.participant_code_prefix and (self.organization_name or "").strip():
            self.participant_code_prefix = self._unique_code_prefix()

        super().save(*args, **kwargs)


class Staff(models.Model):
    """
    Organization staff *membership*: links a CustomUser (one identity per human)
    to an Organization with a role. A single user can be staff in several orgs
    and still own/hold their own profiles — identity is never duplicated.
    """

    class AccountType(models.TextChoices):
        MAKER = "maker"
        CHECKER = "checker"

    class Status(models.TextChoices):
        PENDING = "pending"   # invited, not yet accepted
        ACTIVE = "active"     # accepted / active member
        REVOKED = "revoked"   # access removed

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user_account = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="staff",
        null=True,
        blank=True,
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="staff",
        null=True,
        blank=True,
    )
    account_type = models.CharField(
        max_length=100,
        choices=AccountType.choices,
        default=AccountType.MAKER,
    )
    # Defaults to ACTIVE so pre-existing rows keep working after migration; the
    # invite flow explicitly creates new memberships as PENDING.
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    email = models.EmailField()
    phone_number = PhoneNumberField(blank=True, null=True)
    role = models.CharField(max_length=100, blank=True, null=True)
    bio = models.TextField(blank=True, null=True)

    # Volunteers and administrative helpers assist with data entry but must
    # never be presented as qualified medical personnel (13 July 2026 review,
    # item l). Defaults to False so a new member is non-clinical until an
    # organisation states otherwise.
    is_clinical = models.BooleanField(
        default=False,
        help_text=(
            "Whether this member is a qualified health professional. "
            "Non-clinical members are never displayed as medical personnel."
        ),
    )
    # Capability strings this member is allowed to exercise, e.g.
    # ["record_participants", "view_reports"]. Empty means the defaults for
    # their account_type apply.
    permissions = models.JSONField(default=list, blank=True)

    invited_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def is_active_member(self):
        return self.status == self.Status.ACTIVE

    @property
    def display_role(self):
        """
        Role text safe to show next to a record.

        A non-clinical member's free-text role is shown with a plain
        "Volunteer / Support" qualifier so nobody reading a participant record
        mistakes an assisting volunteer for the clinician who assessed them.
        """
        role = (self.role or "").strip()
        if self.is_clinical:
            return role or "Health Professional"
        return f"{role} (Volunteer / Support)" if role else "Volunteer / Support"

    # Capabilities granted by account type when `permissions` is left empty.
    DEFAULT_PERMISSIONS = {
        AccountType.MAKER: ["record_participants", "view_own_records"],
        AccountType.CHECKER: [
            "record_participants",
            "view_own_records",
            "view_reports",
            "approve_records",
        ],
    }

    def effective_permissions(self):
        if self.permissions:
            return list(self.permissions)
        return list(self.DEFAULT_PERMISSIONS.get(self.account_type, []))

    def has_permission(self, capability: str) -> bool:
        """Access is refused outright once a membership is not active."""
        if not self.is_active_member:
            return False
        return capability in self.effective_permissions()

    class Meta:
        db_table = "staff"
        verbose_name = "Staff"
        verbose_name_plural = "Staff"
        constraints = [
            models.UniqueConstraint(
                fields=["user_account", "organization"],
                name="unique_staff_membership_per_org",
            )
        ]


class OrganizationFiles(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="files",
        null=True,
        blank=True,
    )
    document_type = models.CharField(
        max_length=100,
        choices=[
            ("certificate", "Certificate"),
            ("license", "License"),
            ("other", "Other"),
        ],
        blank=True,
        null=True,
    )
    file = models.FileField(upload_to="organization_files/")
    file_type = models.CharField(max_length=100, blank=True, null=True)
    file_name = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.file_name} - {self.document_type}"


# =============================================================================
# LOCUM NEEDS MODELS
# =============================================================================


class LocumJobRole(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    organization = models.ManyToManyField(
        Organization,
        related_name="locum_job_roles",
        blank=True,
    )
    default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class LocumJob(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)

    # basic information
    role = models.ForeignKey(
        LocumJobRole,
        on_delete=models.SET_NULL,
        related_name="locum_jobs",
        null=True,
    )
    title = models.CharField(max_length=150)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.SET_NULL,
        related_name="locum_jobs",
        null=True,
    )
    description = models.TextField()
    requirements = models.TextField(blank=True)
    location = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, blank=True, null=True)

    # images
    title_image = models.ImageField(
        upload_to="locum_jobs/title_images/",
        blank=True,
        null=True,
    )

    # job type
    job_type = models.CharField(
        max_length=20,
        choices=[
            ("volunteering", "Volunteering"),
            ("paid", "Paid"),
        ],
        default="paid",
    )

    # renumeration (optional for volunteering jobs)
    renumeration = models.DecimalField(
        max_digits=19, decimal_places=2, blank=True, null=True
    )
    renumeration_frequency = models.CharField(
        max_length=20,
        choices=[
            ("hourly", "Hourly"),
            ("daily", "Daily"),
            ("weekly", "Weekly"),
            ("monthly", "Monthly"),
            ("yearly", "Yearly"),
        ],
        blank=True,
        null=True,
    )
    currency = models.CharField(max_length=8, default="GHS", blank=True)

    # Volunteer eligibility (13 July 2026 review, item n). Medical students,
    # data analysts and other non-clinical helpers should be able to apply for
    # suitable volunteer roles, but the organiser decides which roles those
    # are — a clinical role stays restricted even when unpaid.
    open_to_non_professionals = models.BooleanField(
        default=False,
        help_text=(
            "Allow applicants without a health-professional profile. "
            "Only meaningful for volunteering roles."
        ),
    )

    # approval
    is_active = models.BooleanField(default=True)
    approved = models.BooleanField(default=False)

    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    @property
    def accepts_non_professionals(self) -> bool:
        """Non-clinical applicants are only ever eligible for open volunteer roles."""
        return bool(self.job_type == "volunteering" and self.open_to_non_professionals)

    @property
    def is_expired(self):
        """
        A locum job auto-expires once every program it is attached to has
        ended (latest program end_date in the past). Jobs not attached to any
        program never auto-expire.
        """
        from django.utils import timezone

        end_dates = [
            need.program.end_date
            for need in self.locum_needs.all()
            if need.program and need.program.end_date
        ]
        if not end_dates:
            return False
        return max(end_dates) < timezone.now().date()

    @property
    def is_accepting_applications(self):
        """Open to new applications only when active, approved and not expired."""
        return bool(self.is_active and self.approved and not self.is_expired)

    # override save to create unique slug
    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)
            unique_slug = base_slug
            num = 1
            # Check if slug already exists and make it unique
            while LocumJob.objects.filter(slug=unique_slug).exists():
                unique_slug = f"{base_slug}-{num}"
                num += 1
            self.slug = unique_slug
        super().save(*args, **kwargs)


# =============================================================================
# LOCUM JOB APPLICATION MODEL
# =============================================================================


class LocumJobApplication(models.Model):
    """
    Model representing an application submitted for a locum job
    """

    STATUS_SUBMITTED = "submitted"
    STATUS_UNDER_REVIEW = "under_review"
    STATUS_ACCEPTED = "accepted"
    STATUS_REJECTED = "rejected"

    STATUS_CHOICES = [
        (STATUS_SUBMITTED, "Submitted"),
        (STATUS_UNDER_REVIEW, "Under review"),
        (STATUS_ACCEPTED, "Accepted"),
        (STATUS_REJECTED, "Rejected"),
    ]

    class ApplicantType(models.TextChoices):
        """
        Recorded so an organiser reviewing a volunteer role can see at a glance
        who is clinically qualified and who is not, rather than inferring it.
        """

        HEALTH_PROFESSIONAL = "health_professional", "Health Professional"
        STUDENT = "student", "Student / In training"
        NON_PROFESSIONAL = "non_professional", "Non-Health Professional"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    job = models.ForeignKey(
        LocumJob,
        on_delete=models.CASCADE,
        related_name="applications",
    )
    applicant = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="locum_job_applications",
    )
    full_name = models.CharField(max_length=255)
    email = models.EmailField()
    phone_number = PhoneNumberField(blank=True, null=True)
    resume = models.FileField(
        upload_to="locum_jobs/applications/resumes/", blank=True, null=True
    )
    cover_letter = models.TextField(blank=True)
    years_of_experience = models.PositiveIntegerField(blank=True, null=True)

    applicant_type = models.CharField(
        max_length=32,
        choices=ApplicantType.choices,
        default=ApplicantType.HEALTH_PROFESSIONAL,
    )
    # Free-text background for applicants with no professional profile — a data
    # analyst or medical student describing what they bring to the event.
    background = models.TextField(
        blank=True,
        help_text="Relevant skills or background, for non-professional applicants.",
    )

    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_SUBMITTED
    )
    applied_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-applied_at"]
        unique_together = ("job", "applicant")

    def __str__(self):
        return f"{self.full_name} - {self.job.title}"


# =============================================================================
# HEALTH PROGRAM MODELS
# =============================================================================


class HealthProgramType(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    default = models.BooleanField(default=False)
    organizations = models.ManyToManyField(
        Organization,
        related_name="health_program_types",
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class HealthProgramPartners(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name = models.CharField(max_length=255)
    logo = models.ImageField(
        upload_to="health_program_partners/logos/",
        blank=True,
        null=True,
    )
    url = models.URLField(blank=True, null=True)

    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class HealthProgram(models.Model):
    """
    Core model for community health programs/interventions
    """

    STATUS_CHOICES = [
        ("planning", "Planning"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)

    # image
    title_image = models.ImageField(
        upload_to="health_programs/title_images/",
        blank=True,
        null=True,
    )

    # Basic Information
    program_name = models.CharField(max_length=255)
    program_type = models.ForeignKey(
        HealthProgramType,
        on_delete=models.CASCADE,
        related_name="health_programs",
        null=True,
        blank=True,
    )
    description = models.TextField(blank=True)

    # Dates
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)

    # Location
    location_name = models.CharField(max_length=255)
    district = models.CharField(max_length=100)
    region = models.CharField(max_length=100)
    latitude = models.DecimalField(
        max_digits=19, decimal_places=18, null=True, blank=True
    )
    longitude = models.DecimalField(
        max_digits=19, decimal_places=18, null=True, blank=True
    )
    location_details = models.TextField(blank=True)

    # Participants
    target_participants = models.IntegerField(
        help_text="Estimated number of participants"
    )
    actual_participants = models.IntegerField(
        default=0, help_text="Actual number reached"
    )

    # Organization Details
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="health_programs",
        help_text="Community organization managing this program",
        null=True,
        blank=True,
    )
    created_by = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="programs_created"
    )
    partner_organizations = models.ManyToManyField(
        HealthProgramPartners,
        related_name="health_programs_partners",
        blank=True,
    )
    funding_source = models.CharField(max_length=255, blank=True, null=True)

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="planning")

    # Approval fields
    approval_reason = models.TextField(
        blank=True, null=True, help_text="Reason for approving the program"
    )
    approved_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        related_name="programs_approved",
        null=True,
        blank=True,
        help_text="User who approved this program",
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    equipment_needs = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "community_health_programs"
        verbose_name = "Health Program"
        verbose_name_plural = "Health Programs"
        ordering = ["-start_date", "-created_at"]
        indexes = [
            models.Index(fields=["status", "start_date"]),
            models.Index(fields=["program_type"]),
            models.Index(fields=["district", "region"]),
            models.Index(fields=["organization"]),
            models.Index(fields=["created_by"]),
        ]

    def __str__(self):
        return f"{self.program_name} ({self.program_type.name if self.program_type else 'No Type'})"

    @property
    def is_active(self):
        """Check if program is currently active"""
        today = timezone.now().date()
        if self.status != "in_progress":
            return False
        if self.end_date:
            return self.start_date <= today <= self.end_date
        return self.start_date <= today

    @property
    def participation_rate(self):
        """Calculate actual vs target participation"""
        if self.target_participants > 0:
            return round((self.actual_participants / self.target_participants) * 100, 2)
        return 0


class HealthProgramLocumNeed(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    program = models.ForeignKey(
        HealthProgram,
        on_delete=models.CASCADE,
        related_name="locum_needs",
    )
    locum_job = models.ForeignKey(
        LocumJob,
        on_delete=models.CASCADE,
        related_name="locum_needs",
    )
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.program} - {self.locum_job}"


class ProgramInterventionType(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    default = models.BooleanField(default=False)
    organizations = models.ManyToManyField(
        Organization,
        related_name="program_intervention_types",
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class ProgramIntervention(models.Model):
    """
    Individual interventions/services within a health program
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    intervention_type = models.ForeignKey(
        ProgramInterventionType,
        on_delete=models.CASCADE,
        related_name="interventions",
    )

    # The organiser's own name for this intervention, e.g. "Day 2 — Eye
    # Screening (Adults)". The type alone is too coarse: one programme often
    # runs several interventions of the same type and they were previously
    # indistinguishable in every list.
    #
    # Optional, and falls back to the type name via `display_title`, so
    # existing interventions and quick set-ups still read sensibly.
    title = models.CharField(max_length=255, blank=True, default="")

    program = models.ForeignKey(
        HealthProgram,
        on_delete=models.CASCADE,
        related_name="interventions",
    )

    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        related_name="created_interventions",
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "program_interventions"
        verbose_name = "Program Intervention"
        verbose_name_plural = "Program Interventions"
        indexes = [
            models.Index(fields=["program"]),
            models.Index(fields=["intervention_type"]),
        ]

    @property
    def display_title(self) -> str:
        """
        What to show wherever this intervention is named.

        The single place the fallback lives, so a blank title never surfaces as
        an empty heading and callers do not each reinvent the rule.
        """
        title = (self.title or "").strip()
        if title:
            return title
        return self.intervention_type.name if self.intervention_type_id else "Intervention"

    def __str__(self):
        return f"{self.display_title} - {self.program}"


class HealthProgramInvitation(models.Model):
    class InvitationStatus(models.TextChoices):
        PENDING = "PENDING"
        ACCEPTED = "ACCEPTED"
        REJECTED = "REJECTED"
        EXPIRED = "EXPIRED"

    class InvitationSource(models.TextChoices):
        INVITE = "INVITE", "Invite"
        LOCUM = "LOCUM", "Locum"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    program = models.ForeignKey(
        HealthProgram,
        on_delete=models.CASCADE,
        related_name="invitations",
    )
    intervention = models.ManyToManyField(
        ProgramIntervention,
        related_name="invitations",
        blank=True,
    )
    status = models.CharField(
        choices=InvitationStatus.choices,
        default=InvitationStatus.PENDING,
    )
    # How this professional became part of the program: directly invited by the
    # org, or auto-added after their locum application was accepted.
    source = models.CharField(
        max_length=10,
        choices=InvitationSource.choices,
        default=InvitationSource.INVITE,
    )
    # Set when the participation originates from an accepted locum application.
    locum_application = models.ForeignKey(
        "LocumJobApplication",
        on_delete=models.SET_NULL,
        related_name="program_invitations",
        null=True,
        blank=True,
    )
    message = models.TextField(blank=True, null=True)

    expires_at = models.DateTimeField(blank=True, null=True)
    link = models.URLField(blank=True, null=True)
    invited_by = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="invited_by"
    )
    invited_by_user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="invitations_sent",
        null=True,
        blank=True,
        help_text="The user who created the invitation",
    )
    invited_to = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="invited_to"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.program} - {self.invited_by}"


class InterventionField(models.Model):
    class FieldType(models.TextChoices):
        TEXT = "TEXT"
        BOOLEAN = "BOOLEAN"
        NUMBER = "NUMBER"
        SELCTION = "SELECTION"
        DATE = "DATE"

    class Section(models.TextChoices):
        """
        The three-part structure agreed in the 13 July 2026 review: standard
        participant information, configurable vitals, then whatever the
        specific intervention needs.
        """

        PARTICIPANT = "PARTICIPANT", "Participant Information"
        VITALS = "VITALS", "Vitals"
        INTERVENTION = "INTERVENTION", "Intervention-Specific"

    class FieldKey(models.TextChoices):
        """
        Well-known fields the platform treats specially — for unit handling,
        cross-intervention display, and derived values such as BMI.
        """

        HEIGHT = "height", "Height (cm)"
        WEIGHT = "weight", "Weight (kg)"
        BMI = "bmi", "Body Mass Index"
        BLOOD_PRESSURE = "blood_pressure", "Blood Pressure"
        TEMPERATURE = "temperature", "Temperature (°C)"
        PULSE = "pulse", "Pulse (bpm)"
        RESPIRATORY_RATE = "respiratory_rate", "Respiratory Rate"
        BLOOD_SUGAR = "blood_sugar", "Blood Sugar"
        OXYGEN_SATURATION = "oxygen_saturation", "Oxygen Saturation (%)"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    intervention = models.ForeignKey(
        ProgramIntervention,
        on_delete=models.CASCADE,
        related_name="fields",
    )
    field_type = models.CharField(
        choices=FieldType.choices,
        default=FieldType.TEXT,
    )
    section = models.CharField(
        max_length=20,
        choices=Section.choices,
        default=Section.INTERVENTION,
        db_index=True,
    )
    # Optional semantic key. Set for standard clinical measurements so the
    # platform can compute BMI, carry vitals across interventions, and chart
    # them; left blank for free-form fields an organiser invents.
    field_key = models.CharField(
        max_length=32, choices=FieldKey.choices, blank=True, null=True
    )
    # Derived server-side (currently only BMI). The UI renders these read-only.
    is_computed = models.BooleanField(default=False)

    name = models.CharField(max_length=255)
    required = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["section", "order", "date_created"]
        indexes = [
            models.Index(fields=["intervention", "section", "order"]),
        ]

    def save(self, *args, **kwargs):
        # BMI is always derived, never typed in, whoever creates the field.
        if self.field_key == self.FieldKey.BMI:
            self.is_computed = True
        # Blood pressure is recorded as text so "120/80" can be entered as-is.
        if self.field_key == self.FieldKey.BLOOD_PRESSURE:
            self.field_type = self.FieldType.TEXT
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} - {self.intervention}"


class InterventionFieldOption(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    option = models.CharField(max_length=255)
    field = models.ForeignKey(
        InterventionField,
        on_delete=models.CASCADE,
        related_name="options",
    )
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.option} - {self.field}"


def format_participant_number(participant_code, number) -> str:
    """
    Build the code staff read aloud and write on a slip, e.g. "JTQFV-003".

    Pads to three digits but never truncates, so a four-digit number renders
    as "JTQFV-1234" rather than a silently wrong "JTQFV-123".

    Returns the bare code when there is no number. That covers rows created
    before numbers existed and slips printed with no programme.
    """
    code = participant_code or "—"
    if number is None:
        return code
    return f"{code}-{number:03d}"


class Participant(models.Model):
    """
    A person attended to during one health programme.

    Carries the standard participant information that is the same across every
    intervention (name, contact, demographics). Intervention-specific answers
    live in InterventionResponseValue against configurable fields.

    Identity is scoped to one event. A person who attends a second event is
    registered again there and holds a second row. Staff therefore never see
    another event's data while working at this one.
    """

    class Gender(models.TextChoices):
        MALE = "male", "Male"
        FEMALE = "female", "Female"
        OTHER = "other", "Other"
        UNDISCLOSED = "undisclosed", "Prefer not to say"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)

    # Owning organisation — needed to scope the readable participant code and
    # to keep one organisation's participants out of another's records.
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="participants",
        null=True,
        blank=True,
    )
    # The event this participant belongs to. Identity is scoped to one event:
    # a person who attends a second event is registered again there, and holds
    # a separate row. Nullable for rows that predate this field and for queue
    # slips printed without a programme.
    program = models.ForeignKey(
        "HealthProgram",
        on_delete=models.CASCADE,
        related_name="participants",
        null=True,
        blank=True,
    )
    # Short, human-usable ID, e.g. "JTQFV". Unique platform-wide.
    participant_code = models.CharField(
        max_length=20, unique=True, blank=True, null=True, db_index=True
    )
    # The number the participant remembers and says out loud: "I am number 3".
    # It restarts at 1 for every event, so it is short enough to hold in the
    # head. It is unique only inside one event.
    participant_number = models.PositiveIntegerField(null=True, blank=True)

    fullname = models.CharField(max_length=255)
    phone_number = PhoneNumberField(blank=True, null=True)
    email = models.EmailField(blank=True, null=True)

    gender = models.CharField(
        max_length=12, choices=Gender.choices, blank=True, null=True
    )
    # Both are offered: outreach events often capture a stated age rather than
    # a date of birth, but a date of birth stays accurate over time.
    date_of_birth = models.DateField(blank=True, null=True)
    age = models.PositiveSmallIntegerField(
        blank=True,
        null=True,
        help_text="Stated age at registration; ignored when date_of_birth is set.",
    )
    location = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Community, town or district the participant came from.",
    )

    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["organization", "date_created"]),
            models.Index(fields=["phone_number"]),
            # Serves the number search, which is the first branch of every
            # participant lookup.
            models.Index(fields=["program", "participant_number"]),
        ]
        constraints = [
            # Two people at one event must never hold one number. A NULL
            # number is ignored by the constraint, so legacy rows and
            # unnumbered slips can coexist.
            models.UniqueConstraint(
                fields=["program", "participant_number"],
                name="uniq_participant_number_per_program",
            ),
            models.CheckConstraint(
                condition=models.Q(participant_number__gte=1),
                name="participant_number_is_positive",
            ),
        ]

    def __str__(self):
        return f"{self.display_code} · {self.fullname}"

    @property
    def display_code(self) -> str:
        """
        What staff read and write down, for example "JTQFV-003".

        Falls back to the bare code when the participant holds no number, which
        covers rows created before this field and slips printed with no
        programme.
        """
        return format_participant_number(
            self.participant_code, self.participant_number
        )

    @property
    def current_age(self):
        """Age from date of birth when known, else the stated age."""
        if self.date_of_birth:
            today = timezone.localdate()
            return (
                today.year
                - self.date_of_birth.year
                - (
                    (today.month, today.day)
                    < (self.date_of_birth.month, self.date_of_birth.day)
                )
            )
        return self.age

    # Characters a person cannot misread off a paper slip: no O/0, I/1/L,
    # S/5, Z/2. Staff transcribe these by hand under a tent, so an ambiguous
    # glyph is a wrong record, not a typo.
    CODE_ALPHABET = "ABCDEFGHJKMNPQRTUVWXY346789"
    CODE_RANDOM_LENGTH = 4

    def _generate_participant_code(self) -> str:
        """
        Allocate this participant's short, readable identifier.

        Format is the organisation prefix plus four random characters
        ("SJ7K2M") — six or seven in total, unique platform-wide.

        The prefix is used whole rather than trimmed to a fixed width: an
        organisation whose two-letter form was already taken holds a
        three-letter one, and shortening it here would hand two different
        organisations the same visible prefix.

        The random tail matters now that the code, not the phone number, is the
        handle used to find someone: codes were previously sequential, so
        anyone holding one slip could count upwards and pull every other
        participant's name, phone, age and location out of the lookup endpoint.
        """
        prefix = (
            self.organization.ensure_code_prefix() if self.organization else "BC"
        )

        # The unique constraint is the real arbiter; this just avoids losing a
        # save to a collision that is cheap to detect first.
        for _ in range(12):
            candidate = prefix + "".join(
                secrets.choice(self.CODE_ALPHABET)
                for _ in range(self.CODE_RANDOM_LENGTH)
            )
            if not Participant.objects.filter(participant_code=candidate).exists():
                return candidate

        # 27^4 exhausted for this prefix (~530k participants in one org) —
        # widen rather than fail the registration.
        return prefix + "".join(
            secrets.choice(self.CODE_ALPHABET)
            for _ in range(self.CODE_RANDOM_LENGTH + 2)
        )

    def save(self, *args, **kwargs):
        # Assigned unconditionally: the code is now the primary way to find a
        # participant, so a row without one is unreachable. It used to be
        # skipped when no organisation was set, which left those rows with no
        # identifier at all once the phone number became optional.
        if not self.participant_code:
            self.participant_code = self._generate_participant_code()
        super().save(*args, **kwargs)


class InterventionResponse(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    patient_record = models.ForeignKey(
        "patients.PatientProfile",
        on_delete=models.SET_NULL,
        related_name="intervention_field_responses",
        null=True,
        blank=True,
    )
    participant = models.ForeignKey(
        Participant,
        on_delete=models.SET_NULL,
        related_name="intervention_responses",
        null=True,
    )
    intervention = models.ForeignKey(
        ProgramIntervention,
        on_delete=models.SET_NULL,
        related_name="intervention_responses",
        null=True,
    )
    # Who recorded / last edited this response (org staff). Null for anonymous
    # public-form submissions. Response-level attribution only.
    created_by = models.ForeignKey(
        "accounts.CustomUser",
        on_delete=models.SET_NULL,
        related_name="created_intervention_responses",
        null=True,
        blank=True,
    )
    updated_by = models.ForeignKey(
        "accounts.CustomUser",
        on_delete=models.SET_NULL,
        related_name="updated_intervention_responses",
        null=True,
        blank=True,
    )

    # When the measurement was actually taken, as distinct from when it was
    # keyed in. Large outreach events run on paper slips and are transcribed
    # later (13 July 2026 review, item k); without this, every record from a
    # day's event would carry the timestamp of the evening it was typed up,
    # and post-event reporting would be wrong.
    recorded_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the data was collected. Defaults to the entry time.",
    )
    # Marks a record transcribed from paper rather than captured live.
    entry_mode = models.CharField(
        max_length=16,
        choices=[
            ("live", "Captured live"),
            ("transcribed", "Transcribed from paper"),
            ("imported", "Bulk imported"),
        ],
        default="live",
    )

    # Offline sync (13 July 2026 review, item b). Generated on the device when
    # the record is first saved locally. Unique, so replaying a queued item
    # after a flaky connection can never create a duplicate — the retry that
    # follows a timed-out request is the normal case, not the exception.
    client_uuid = models.UUIDField(
        null=True,
        blank=True,
        unique=True,
        db_index=True,
        help_text="Client-generated id used to de-duplicate offline submissions.",
    )
    synced_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this record arrived from an offline queue.",
    )

    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Fall back to entry time so `recorded_at` is always safe to report on.
        if self.recorded_at is None and self.date_created:
            self.recorded_at = self.date_created
        super().save(*args, **kwargs)
        if self.recorded_at is None:
            # First save: date_created only exists after the insert.
            InterventionResponse.objects.filter(pk=self.pk).update(
                recorded_at=self.date_created
            )
            self.recorded_at = self.date_created

    def __str__(self):
        return f"{self.participant} - {self.intervention}"


class InterventionResponseValue(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    # link it to  a participant
    response = models.ForeignKey(
        InterventionResponse,
        on_delete=models.SET_NULL,
        related_name="response_values",
        null=True,
    )

    field = models.ForeignKey(
        InterventionField,
        on_delete=models.SET_NULL,
        related_name="responses",
        null=True,
    )
    value = models.TextField()

    # When this particular measurement was taken. Field-level rather than
    # response-level because two people may contribute to the same record: a
    # nurse takes vitals, a doctor adds findings later. Sync compares this so a
    # stale value queued offline never overwrites a fresher one already synced
    # (13 July 2026 review, item b).
    recorded_at = models.DateTimeField(null=True, blank=True, db_index=True)
    # Who last wrote this value, so an overwrite is attributable.
    recorded_by = models.ForeignKey(
        "accounts.CustomUser",
        on_delete=models.SET_NULL,
        related_name="recorded_response_values",
        null=True,
        blank=True,
    )

    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.field} - {self.value}"


class InterventionTemplate(models.Model):
    """
    A reusable set of fields for a common intervention (general screening, eye
    screening, BP check…).

    Organisers pick a template when creating an intervention and get its fields
    pre-populated, then edit them for the specific event — the template itself
    is never mutated by that editing.

    Platform templates (`organization` null, `is_platform_default` true) are
    available to everyone; an organisation can also save its own.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    intervention_type = models.ForeignKey(
        ProgramInterventionType,
        on_delete=models.SET_NULL,
        related_name="templates",
        null=True,
        blank=True,
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="intervention_templates",
        null=True,
        blank=True,
        help_text="Null for platform-wide templates available to every organisation.",
    )
    is_platform_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        related_name="created_intervention_templates",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "intervention_templates"
        verbose_name = "Intervention Template"
        verbose_name_plural = "Intervention Templates"
        ordering = ["-is_platform_default", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "name"],
                name="unique_template_name_per_org",
            ),
        ]

    def __str__(self):
        scope = "Platform" if self.is_platform_default else str(self.organization)
        return f"{self.name} ({scope})"


class InterventionTemplateField(models.Model):
    """One field definition inside an InterventionTemplate."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    template = models.ForeignKey(
        InterventionTemplate,
        on_delete=models.CASCADE,
        related_name="fields",
    )
    name = models.CharField(max_length=255)
    field_type = models.CharField(
        max_length=20,
        choices=InterventionField.FieldType.choices,
        default=InterventionField.FieldType.TEXT,
    )
    section = models.CharField(
        max_length=20,
        choices=InterventionField.Section.choices,
        default=InterventionField.Section.INTERVENTION,
    )
    field_key = models.CharField(
        max_length=32,
        choices=InterventionField.FieldKey.choices,
        blank=True,
        null=True,
    )
    is_computed = models.BooleanField(default=False)
    required = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    # Choices for SELECTION fields, stored inline rather than as another table.
    options = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = "intervention_template_fields"
        ordering = ["section", "order", "name"]

    def __str__(self):
        return f"{self.name} · {self.template.name}"


class BulkInterventionUpload(models.Model):
    """
    Track bulk uploads of intervention data
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("partial", "Partially Completed"),
    ]

    program = models.ForeignKey(
        HealthProgram, on_delete=models.CASCADE, related_name="bulk_uploads"
    )
    uploaded_by = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="bulk_uploads"
    )
    file = models.FileField(upload_to="bulk_uploads/interventions/")
    file_name = models.CharField(max_length=255)

    # Processing status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    total_rows = models.IntegerField(default=0)
    processed_rows = models.IntegerField(default=0)
    successful_rows = models.IntegerField(default=0)
    failed_rows = models.IntegerField(default=0)

    # Error tracking
    errors = models.JSONField(default=list, blank=True)
    processing_log = models.TextField(blank=True)

    # Timestamps
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "bulk_intervention_uploads"
        verbose_name = "Bulk Intervention Upload"
        verbose_name_plural = "Bulk Intervention Uploads"
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"Bulk Upload - {self.file_name} ({self.status})"


# =============================================================================
# HEALTH SURVEY MODELS
# =============================================================================


class SurveyType(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    default = models.BooleanField(default=False)
    organizations = models.ManyToManyField(
        Organization,
        related_name="survey_types",
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Survey(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    title = models.CharField(max_length=240)
    description = models.TextField()
    survey_type = models.ForeignKey(
        SurveyType,
        on_delete=models.SET_NULL,
        related_name="surveys",
        null=True,
    )
    end_date = models.DateField()
    active = models.BooleanField(default=True)

    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        CustomUser, related_name="surveys", on_delete=models.SET_NULL, null=True
    )

    def __str__(self):
        return str(self.title)

    class Meta:
        ordering = ["-date_created"]


class SurveyQuestion(models.Model):
    class QuestionType(models.TextChoices):
        TEXT = "TEXT"
        BOOLEAN = "BOOLEAN"
        NUMBER = "NUMBER"
        SELCTION = "SELECTION"
        DATE = "DATE"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    survey = models.ForeignKey(
        Survey,
        related_name="questions",
        on_delete=models.CASCADE,
    )
    question_type = models.CharField(choices=QuestionType.choices)
    question = models.CharField(max_length=240)
    required = models.BooleanField(default=False)

    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    uuid = models.UUIDField(unique=True, blank=True, null=True, default=uuid.uuid4)

    def __str__(self):
        return str(self.question)

    class Meta:
        ordering = ["-date_created"]


class SurveyQuestionOption(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    option = models.CharField(max_length=240)
    question = models.ForeignKey(
        SurveyQuestion,
        related_name="options",
        on_delete=models.CASCADE,
    )

    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    uuid = models.UUIDField(unique=True, blank=True, null=True, default=uuid.uuid4)

    def __str__(self):
        return str(self.option)


class SurveyResponse(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    survey = models.ForeignKey(
        Survey,
        related_name="responses",
        on_delete=models.CASCADE,
    )
    phone_number = PhoneNumberField(blank=True, null=True)

    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return str(self.phone_number)

    class Meta:
        ordering = ["-date_created"]


class SurveyResponseAnswers(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    response = models.ForeignKey(
        SurveyResponse,
        related_name="answers",
        on_delete=models.CASCADE,
    )
    question = models.ForeignKey(
        SurveyQuestion,
        related_name="answers",
        on_delete=models.CASCADE,
    )
    answer = models.TextField()

    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return str(self.answer)

    class Meta:
        ordering = (
            "response",
            "question",
            "date_created",
        )


class BulkSurveyUpload(models.Model):
    """
    Track bulk uploads of survey responses
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("partial", "Partially Completed"),
    ]

    survey = models.ForeignKey(
        Survey, on_delete=models.CASCADE, related_name="bulk_uploads"
    )
    uploaded_by = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="survey_bulk_uploads"
    )
    file = models.FileField(upload_to="bulk_uploads/surveys/")
    file_name = models.CharField(max_length=255)

    # Processing status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    total_rows = models.IntegerField(default=0)
    processed_rows = models.IntegerField(default=0)
    successful_rows = models.IntegerField(default=0)
    failed_rows = models.IntegerField(default=0)

    # Error tracking
    errors = models.JSONField(default=list, blank=True)
    processing_log = models.TextField(blank=True)

    # Timestamps
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "bulk_survey_uploads"
        verbose_name = "Bulk Survey Upload"
        verbose_name_plural = "Bulk Survey Uploads"
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"Bulk Survey Upload - {self.file_name} ({self.status})"


# =============================================================================
# CERTIFICATE MODELS
# =============================================================================


class CertificateTemplate(models.Model):
    class TemplateType(models.TextChoices):
        BUILTIN = "builtin", "Built-in Design"
        IMAGE_OVERLAY = "image_overlay", "Image Overlay"
        PDF_PLACEHOLDER = "pdf_placeholder", "PDF with Placeholders"

    class BuiltinStyle(models.TextChoices):
        CLASSIC = "classic", "Classic"
        PROFESSIONAL = "professional", "Professional"
        MODERN = "modern", "Modern"
        ELEGANT = "elegant", "Elegant"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="certificate_templates",
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    template_type = models.CharField(
        max_length=20,
        choices=TemplateType.choices,
        default=TemplateType.BUILTIN,
    )
    builtin_style = models.CharField(
        max_length=20,
        choices=BuiltinStyle.choices,
        default=BuiltinStyle.CLASSIC,
        blank=True,
    )
    background_image = models.ImageField(
        upload_to="certificate_templates/backgrounds/",
        blank=True,
        null=True,
    )
    pdf_template = models.FileField(
        upload_to="certificate_templates/pdf/",
        blank=True,
        null=True,
    )
    primary_color = models.CharField(max_length=7, default="#009EDB")
    secondary_color = models.CharField(max_length=7, default="#00c7a6")
    accent_color = models.CharField(max_length=7, default="#7733FF")
    custom_logo = models.ImageField(
        upload_to="certificate_templates/logos/",
        blank=True,
        null=True,
    )
    header_text = models.CharField(max_length=255, default="Certificate of Participation")
    body_text = models.TextField(
        default=(
            "This is to certify that {{participant_name}} has successfully participated "
            "in {{program_name}} organized by {{organization_name}} from {{start_date}} to {{end_date}}."
        )
    )
    footer_text = models.CharField(max_length=255, blank=True, default="")
    signatory_name = models.CharField(max_length=255, blank=True, default="")
    signatory_title = models.CharField(max_length=255, blank=True, default="")
    signatory_signature = models.ImageField(
        upload_to="certificate_templates/signatures/",
        blank=True,
        null=True,
    )
    show_qr_code = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "certificate_templates"
        verbose_name = "Certificate Template"
        verbose_name_plural = "Certificate Templates"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.organization.organization_name})"


class IssuedCertificate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    program = models.ForeignKey(
        HealthProgram,
        on_delete=models.CASCADE,
        related_name="issued_certificates",
    )
    invitation = models.OneToOneField(
        HealthProgramInvitation,
        on_delete=models.SET_NULL,
        related_name="certificate",
        null=True,
        blank=True,
    )
    template = models.ForeignKey(
        CertificateTemplate,
        on_delete=models.SET_NULL,
        related_name="issued_certificates",
        null=True,
    )
    recipient_name = models.CharField(max_length=255)
    recipient_email = models.EmailField()
    issued_at = models.DateTimeField(auto_now_add=True)
    issued_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        related_name="certificates_issued",
        null=True,
    )
    certificate_file = models.FileField(
        upload_to="issued_certificates/",
        blank=True,
        null=True,
    )
    verification_hash = models.CharField(max_length=64, unique=True)
    verification_code = models.CharField(max_length=12, unique=True)
    is_emailed = models.BooleanField(default=False)
    emailed_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "issued_certificates"
        verbose_name = "Issued Certificate"
        verbose_name_plural = "Issued Certificates"
        ordering = ["-issued_at"]

    def __str__(self):
        return f"Certificate for {self.recipient_name} — {self.program.program_name}"
#         read_only_fields = ("id", "date_created", "last_updated")
