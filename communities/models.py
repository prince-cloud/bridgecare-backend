from django.db import models
from django.utils import timezone
from accounts.models import CustomUser
from phonenumber_field.modelfields import PhoneNumberField
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

    # orgnaization profile
    orgnaization_logo = models.ImageField(
        upload_to="orgnaization_logos/", blank=True, null=True
    )
    verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "organizations"
        verbose_name = "Organization"
        verbose_name_plural = "Organizations"

    def __str__(self):
        return f"{self.user.email} - {self.organization_name or 'Organization'}"


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

    # images
    title_image = models.ImageField(
        upload_to="locum_jobs/title_images/",
        blank=True,
        null=True,
    )

    # renumeration
    renumeration = models.DecimalField(max_digits=19, decimal_places=2)
    renumeration_frequency = models.CharField(
        max_length=20,
        choices=[
            ("hourly", "Hourly"),
            ("daily", "Daily"),
            ("weekly", "Weekly"),
            ("monthly", "Monthly"),
            ("yearly", "Yearly"),
        ],
    )

    # approval
    is_active = models.BooleanField(default=True)
    approved = models.BooleanField(default=False)

    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title


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
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)

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
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
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

    program = models.OneToOneField(
        HealthProgram,
        on_delete=models.CASCADE,
        related_name="intervention",
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

    def __str__(self):
        return f"{self.intervention_type} - {self.program}"


class InterventionField(models.Model):
    class FieldType(models.TextChoices):
        TEXT = "TEXT"
        NUMBER = "NUMBER"
        DATE = "DATE"

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
    name = models.CharField(max_length=255)
    required = models.BooleanField(default=False)

    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

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


class InterventionResponse(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    patient_record = models.ForeignKey(
        "patients.PatientProfile",
        on_delete=models.SET_NULL,
        related_name="intervention_field_responses",
        null=True,
        blank=True,
    )
    participant_id = PhoneNumberField(
        blank=True,
        null=True,
        help_text="The phone number of the participant",
    )
    intervention = models.ForeignKey(
        ProgramIntervention,
        on_delete=models.SET_NULL,
        related_name="intervention_responses",
        null=True,
    )
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.participant} - {self.intervention}"


class InterventionResponseValue(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    # link it to  a participant
    participant = models.ForeignKey(
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
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.field} - {self.value}"


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
        MULTIPLE_CHOICE = "MULTIPLE CHOICE"
        MULTIPLE_SELECT = "MULTIPLE SELECT"

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
