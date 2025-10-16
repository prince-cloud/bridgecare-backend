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

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
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
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
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
    file_type = models.CharField(max_length=10, blank=True, null=True)
    file_name = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.file_name} - {self.document_type}"


# =============================================================================
# HEALTH PROGRAM MODELS
# =============================================================================


class HealthProgramType(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
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

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

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

    # Interventions
    interventions_planned = models.JSONField(
        default=list,
        blank=True,
        help_text="List of planned interventions (vitals, tests, vaccines, etc.)",
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
    lead_organizer = models.CharField(max_length=255)
    lead_organizer_contact = PhoneNumberField(blank=True, null=True)
    partner_organizations = models.JSONField(
        default=list, blank=True, help_text="List of partner organization names"
    )
    funding_source = models.CharField(max_length=255, blank=True)

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="planning")

    # Collaborators
    team_members = models.ManyToManyField(
        CustomUser, related_name="programs_collaborated", blank=True
    )

    # Offline sync
    is_synced = models.BooleanField(default=True)
    offline_id = models.CharField(max_length=100, blank=True, null=True, unique=True)

    # optional fields
    locum_needs = models.JSONField(
        default=list,
        blank=True,
        help_text="List of required roles: {role, quantity, duration}",
    )
    equipment_needs = models.TextField(blank=True)
    equipment_list = models.JSONField(default=list, blank=True)

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
        return f"{self.program_name} ({self.get_program_type_display()})"

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


class ProgramIntervention(models.Model):
    """
    Individual interventions/services within a health program
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    INTERVENTION_TYPE_CHOICES = [
        ("vitals", "Vitals Collection"),
        ("diagnostic", "Diagnostic Test"),
        ("vaccination", "Vaccination"),
        ("telehealth", "Telehealth Session"),
        ("health_tips", "Health Tips Distribution"),
        ("referral", "Referral"),
        ("other", "Other"),
    ]

    program = models.ForeignKey(
        HealthProgram, on_delete=models.CASCADE, related_name="interventions"
    )
    intervention_type = models.CharField(
        max_length=50, choices=INTERVENTION_TYPE_CHOICES
    )
    intervention_name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    # Participant Information
    participant_id = models.CharField(
        max_length=100, blank=True, help_text="Links to EHR if available"
    )
    participant_name = models.CharField(max_length=255, blank=True)
    participant_age = models.IntegerField(null=True, blank=True)
    participant_gender = models.CharField(
        max_length=20,
        choices=[("male", "Male"), ("female", "Female"), ("other", "Other")],
        blank=True,
    )
    participant_phone = PhoneNumberField(blank=True, null=True)

    # Vitals Data
    blood_pressure = models.CharField(
        max_length=20, blank=True, help_text="Format: 120/80"
    )
    temperature = models.DecimalField(
        max_digits=4, decimal_places=1, null=True, blank=True, help_text="In Celsius"
    )
    pulse = models.IntegerField(null=True, blank=True, help_text="Beats per minute")
    weight = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True, help_text="In kg"
    )
    height = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True, help_text="In cm"
    )

    # Test Results
    test_results = models.JSONField(
        default=dict,
        blank=True,
        help_text="Test name and results (e.g., Malaria RDT: Positive)",
    )

    # Vaccination Data
    vaccine_administered = models.CharField(max_length=200, blank=True)
    vaccine_dose_number = models.IntegerField(null=True, blank=True)
    vaccine_batch_number = models.CharField(max_length=100, blank=True)
    vaccination_date = models.DateField(null=True, blank=True)

    # Clinical Information
    symptoms = models.JSONField(default=list, blank=True)
    diagnosis = models.TextField(blank=True)
    treatment_given = models.TextField(blank=True)
    referral_needed = models.BooleanField(default=False)
    referral_facility = models.ForeignKey(
        "facilities.Facility", on_delete=models.SET_NULL, null=True, blank=True
    )
    referral_notes = models.TextField(blank=True)

    # Additional Notes
    notes = models.TextField(blank=True)
    follow_up_required = models.BooleanField(default=False)
    follow_up_date = models.DateField(null=True, blank=True)

    # Metadata
    documented_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        related_name="interventions_documented",
    )
    documented_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # EHR Sync
    synced_to_ehr = models.BooleanField(default=False)
    ehr_record_id = models.CharField(max_length=100, blank=True)

    # Offline support
    offline_id = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        db_table = "program_interventions"
        verbose_name = "Program Intervention"
        verbose_name_plural = "Program Interventions"
        ordering = ["-documented_at"]
        indexes = [
            models.Index(fields=["program", "documented_at"]),
            models.Index(fields=["participant_id"]),
            models.Index(fields=["intervention_type"]),
        ]

    def __str__(self):
        return f"{self.intervention_name} - {self.participant_name or 'Anonymous'}"


class BulkInterventionUpload(models.Model):
    """
    Track bulk uploads of intervention data
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
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
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
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
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
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

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
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
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
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
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
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
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
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

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
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
