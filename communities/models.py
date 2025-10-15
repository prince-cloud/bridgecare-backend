from django.db import models
from django.utils import timezone
from accounts.models import CustomUser
from phonenumber_field.modelfields import PhoneNumberField
import uuid


# =============================================================================
# COMMUNITY PROFILE MODEL
# =============================================================================


class CommunityProfile(models.Model):
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
    volunteer_status = models.BooleanField(default=False)
    coordinator_level = models.CharField(
        max_length=50, blank=True, null=True
    )  # Lead, Assistant, Volunteer
    areas_of_focus = models.JSONField(
        default=list, blank=True
    )  # Health areas they work in

    # Contact information for organization
    organization_phone = PhoneNumberField(blank=True, null=True)
    organization_email = models.EmailField(blank=True, null=True)
    organization_address = models.TextField(blank=True, null=True)

    # Programs and activities
    active_programs = models.JSONField(default=list, blank=True)
    certifications = models.JSONField(default=list, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "community_profiles"
        verbose_name = "Community Profile"
        verbose_name_plural = "Community Profiles"

    def __str__(self):
        return f"{self.user.email} - {self.organization_name or 'Community Profile'}"


# =============================================================================
# HEALTH PROGRAM MODELS
# =============================================================================


class HealthProgram(models.Model):
    """
    Core model for community health programs/interventions
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    PROGRAM_TYPE_CHOICES = [
        ("screening", "Health Screening"),
        ("vaccination", "Vaccination Drive"),
        ("maternal_child", "Maternal/Child Health"),
        ("telehealth", "Group Telehealth"),
        ("health_education", "Health Education Campaign"),
        ("other", "Other"),
    ]

    STATUS_CHOICES = [
        ("planning", "Planning"),
        ("approved", "Approved"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    # Basic Information
    program_name = models.CharField(max_length=255)
    program_type = models.CharField(max_length=50, choices=PROGRAM_TYPE_CHOICES)
    program_type_custom = models.CharField(
        max_length=100, blank=True, help_text="If 'Other' is selected"
    )
    description = models.TextField(blank=True)

    # Dates
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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
        CommunityProfile,
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


class HealthSurvey(models.Model):
    """
    Customizable health surveys for communities
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    SURVEY_TYPE_CHOICES = [
        ("needs_assessment", "Health Needs Assessment"),
        ("impact_evaluation", "Program Impact Evaluation"),
        ("satisfaction", "Satisfaction Survey"),
        ("awareness", "Health Awareness Survey"),
        ("screening", "Pre-Screening Survey"),
        ("custom", "Custom Survey"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("active", "Active"),
        ("closed", "Closed"),
        ("archived", "Archived"),
    ]

    # Basic Information
    title = models.CharField(max_length=255)
    description = models.TextField()
    survey_type = models.CharField(max_length=50, choices=SURVEY_TYPE_CHOICES)

    # Program Association (optional)
    program = models.ForeignKey(
        HealthProgram,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="surveys",
    )

    # Survey Structure
    questions = models.JSONField(
        default=list,
        help_text="List of questions with type, options, validation",
    )

    # Target Audience
    target_audience = models.CharField(max_length=255, blank=True)
    target_count = models.IntegerField(
        default=0, help_text="Expected number of responses"
    )
    actual_responses = models.IntegerField(default=0)

    # Settings
    is_anonymous = models.BooleanField(default=True)
    allow_multiple_responses = models.BooleanField(default=False)
    requires_authentication = models.BooleanField(default=False)

    # Language
    primary_language = models.CharField(max_length=10, default="en")
    available_languages = models.JSONField(
        default=list, help_text="List of language codes"
    )

    # Status and Timing
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    # Metadata
    created_by = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="surveys_created"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Offline support
    supports_offline = models.BooleanField(default=True)

    class Meta:
        db_table = "health_surveys"
        verbose_name = "Health Survey"
        verbose_name_plural = "Health Surveys"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "start_date"]),
            models.Index(fields=["survey_type"]),
        ]

    def __str__(self):
        return f"{self.title} ({self.get_survey_type_display()})"

    @property
    def response_rate(self):
        """Calculate response rate"""
        if self.target_count > 0:
            return round((self.actual_responses / self.target_count) * 100, 2)
        return 0


class SurveyResponse(models.Model):
    """
    Individual responses to health surveys
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    survey = models.ForeignKey(
        HealthSurvey, on_delete=models.CASCADE, related_name="responses"
    )

    # Respondent Information (optional)
    respondent = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="survey_responses",
    )
    respondent_name = models.CharField(max_length=255, blank=True)
    respondent_age = models.IntegerField(null=True, blank=True)
    respondent_gender = models.CharField(max_length=20, blank=True)
    respondent_location = models.CharField(max_length=255, blank=True)

    # Response Data
    answers = models.JSONField(help_text="Question ID: Answer mapping")

    # Metadata
    language_used = models.CharField(max_length=10, default="en")
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    # Offline support
    offline_id = models.CharField(max_length=100, blank=True, null=True)
    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "survey_responses"
        verbose_name = "Survey Response"
        verbose_name_plural = "Survey Responses"
        ordering = ["-submitted_at"]
        indexes = [
            models.Index(fields=["survey", "submitted_at"]),
        ]

    def __str__(self):
        return f"Response to {self.survey.title} - {self.submitted_at}"


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
        HealthSurvey, on_delete=models.CASCADE, related_name="bulk_uploads"
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
# PROGRAM ANALYTICS AND REPORTING
# =============================================================================


class ProgramReport(models.Model):
    """
    Generated reports for health programs (for donors/stakeholders)
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    REPORT_TYPE_CHOICES = [
        ("impact", "Impact Report"),
        ("financial", "Financial Report"),
        ("attendance", "Attendance Report"),
        ("health_outcomes", "Health Outcomes Report"),
        ("custom", "Custom Report"),
    ]

    program = models.ForeignKey(
        HealthProgram, on_delete=models.CASCADE, related_name="reports"
    )
    report_type = models.CharField(max_length=50, choices=REPORT_TYPE_CHOICES)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    # Report Data
    report_data = models.JSONField(
        default=dict, help_text="Aggregated statistics and metrics"
    )
    charts = models.JSONField(
        default=list, blank=True, help_text="Chart configurations"
    )

    # Period
    start_date = models.DateField()
    end_date = models.DateField()

    # Generated Report
    report_file = models.FileField(upload_to="reports/programs/", null=True, blank=True)

    # Metadata
    generated_by = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="reports_generated"
    )
    generated_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "program_reports"
        verbose_name = "Program Report"
        verbose_name_plural = "Program Reports"
        ordering = ["-generated_at"]

    def __str__(self):
        return f"{self.title} - {self.program.program_name}"
