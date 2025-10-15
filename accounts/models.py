from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from phonenumber_field.modelfields import PhoneNumberField
from django.contrib.auth.models import Permission
import uuid


# Platform Choices
PLATFORM_CHOICES = [
    ("communities", "Communities"),
    ("facilities", "Health Facilities"),
    ("professionals", "Individual Professionals"),
    ("partners", "Partners"),
    ("pharmacies", "Pharmacies"),
    ("patients", "Patients/Users"),
]

# Verification Level Choices
VERIFICATION_LEVEL_CHOICES = [
    ("basic", "Basic"),
    ("verified", "Verified"),
    ("professional", "Professional"),
    ("admin", "Administrator"),
]

# MFA Method Choices
MFA_METHOD_CHOICES = [
    ("sms", "SMS"),
    ("email", "Email"),
    ("totp", "TOTP"),
    ("disabled", "Disabled"),
]

# Professional Role Choices
PROFESSIONAL_ROLE_CHOICES = [
    ("doctor", "Doctor"),
    ("nurse", "Nurse"),
    ("midwife", "Midwife"),
    ("pharmacist", "Pharmacist"),
    ("community_health_worker", "Community Health Worker"),
    ("medical_assistant", "Medical Assistant"),
    ("lab_technician", "Lab Technician"),
    ("radiologist", "Radiologist"),
    ("other", "Other"),
]


class CustomUser(AbstractUser):
    """
    Enhanced User model supporting multi-platform authentication
    """

    # Basic Information
    phone_number = PhoneNumberField(blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    profile_picture = models.ImageField(upload_to="profiles/", blank=True, null=True)

    # Platform & Role Management
    platform = models.CharField(
        max_length=20, choices=PLATFORM_CHOICES, default="patients"
    )
    primary_role = models.CharField(
        max_length=50, choices=PROFESSIONAL_ROLE_CHOICES, default="other"
    )
    is_verified = models.BooleanField(default=False)
    verification_level = models.CharField(
        max_length=20, choices=VERIFICATION_LEVEL_CHOICES, default="basic"
    )

    # Professional Information (for healthcare workers)
    license_number = models.CharField(max_length=100, blank=True, null=True)
    license_expiry = models.DateField(blank=True, null=True)
    specializations = models.JSONField(default=list, blank=True)

    # Security & Compliance
    mfa_enabled = models.BooleanField(default=False)
    mfa_method = models.CharField(
        max_length=20, choices=MFA_METHOD_CHOICES, default="disabled"
    )
    last_login_ip = models.GenericIPAddressField(blank=True, null=True)
    login_attempts = models.IntegerField(default=0)
    account_locked_until = models.DateTimeField(blank=True, null=True)

    # Audit Fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_activity = models.DateTimeField(auto_now=True)

    # Additional fields
    is_active = models.BooleanField(default=True)
    otp = models.CharField(max_length=6, blank=True, null=True)
    otp_expiry = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "auth_user"
        verbose_name = "User"
        verbose_name_plural = "Users"

    def __str__(self):
        return self.email or self.username

    def is_account_locked(self):
        """Check if account is currently locked"""
        if self.account_locked_until:
            return timezone.now() < self.account_locked_until
        return False

    def lock_account(self, duration_minutes=30):
        """Lock account for specified duration"""
        self.account_locked_until = timezone.now() + timezone.timedelta(
            minutes=duration_minutes
        )
        self.save()

    def unlock_account(self):
        """Unlock account and reset login attempts"""
        self.account_locked_until = None
        self.login_attempts = 0
        self.save()

    def increment_login_attempts(self):
        """Increment failed login attempts"""
        self.login_attempts += 1
        if self.login_attempts >= 5:  # Lock after 5 attempts
            self.lock_account()
        self.save()

    def reset_login_attempts(self):
        """Reset login attempts on successful login"""
        self.login_attempts = 0
        self.save()


class UserProfile(models.Model):
    """
    Platform-specific user profiles extending the base user
    """

    user = models.OneToOneField(
        CustomUser, on_delete=models.CASCADE, related_name="profile"
    )
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES)

    # Common profile fields
    bio = models.TextField(blank=True, null=True)
    location = models.CharField(max_length=200, blank=True, null=True)
    preferred_language = models.CharField(max_length=10, default="en")

    # Platform-specific JSON data
    profile_data = models.JSONField(default=dict, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "user_profiles"
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"

    def __str__(self):
        return f"{self.user.email} - {self.platform}"


# =============================================================================
# ROLE AND PERMISSION MODELS
# =============================================================================


class Role(models.Model):
    """
    Platform-specific roles with associated permissions
    """

    name = models.CharField(max_length=50, unique=True)
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES)
    description = models.TextField(blank=True, null=True)
    permissions = models.JSONField(default=list, blank=True)  # List of permission codes
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "roles"
        verbose_name = "Role"
        verbose_name_plural = "Roles"
        unique_together = ["name", "platform"]

    def __str__(self):
        return f"{self.name} ({self.platform})"


class UserRole(models.Model):
    """
    User role assignments with facility context for facility-specific roles
    """

    user = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="user_roles"
    )
    role = models.ForeignKey(
        Role, on_delete=models.CASCADE, related_name="user_assignments"
    )
    facility = models.ForeignKey(
        "facilities.Facility",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="role_assignments",
    )
    assigned_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="assigned_roles",
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "user_roles"
        verbose_name = "User Role"
        verbose_name_plural = "User Roles"
        unique_together = ["user", "role", "facility"]

    def __str__(self):
        facility_str = f" at {self.facility.name}" if self.facility else ""
        return f"{self.user.email} - {self.role.name}{facility_str}"

    def is_expired(self):
        """Check if role assignment has expired"""
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False


# =============================================================================
# SECURITY AND MFA MODELS
# =============================================================================


class MFADevice(models.Model):
    """
    Multi-Factor Authentication devices for users
    """

    DEVICE_TYPES = [
        ("sms", "SMS"),
        ("email", "Email"),
        ("totp", "TOTP"),
        ("backup_codes", "Backup Codes"),
    ]

    user = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="mfa_devices"
    )
    device_type = models.CharField(max_length=20, choices=DEVICE_TYPES)
    device_id = models.CharField(max_length=100)  # Phone number, email, or TOTP secret
    device_name = models.CharField(
        max_length=100, blank=True, null=True
    )  # User-friendly name
    is_verified = models.BooleanField(default=False)
    is_primary = models.BooleanField(default=False)
    last_used = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "mfa_devices"
        verbose_name = "MFA Device"
        verbose_name_plural = "MFA Devices"
        unique_together = ["user", "device_id"]

    def __str__(self):
        return f"{self.user.email} - {self.device_type} ({self.device_name or self.device_id})"


class LoginSession(models.Model):
    """
    Track active login sessions for security monitoring
    """

    user = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="login_sessions"
    )
    session_token = models.CharField(max_length=255, unique=True)
    refresh_token = models.CharField(max_length=255, blank=True, null=True)
    device_info = models.JSONField(default=dict, blank=True)  # Browser, OS, device type
    ip_address = models.GenericIPAddressField()
    location = models.JSONField(default=dict, blank=True)  # Country, city, coordinates
    user_agent = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    last_activity = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "login_sessions"
        verbose_name = "Login Session"
        verbose_name_plural = "Login Sessions"

    def __str__(self):
        return f"{self.user.email} - {self.ip_address} ({self.created_at})"

    def is_expired(self):
        """Check if session has expired"""
        return timezone.now() > self.expires_at


class SecurityEvent(models.Model):
    """
    Track security-related events for monitoring and alerting
    """

    EVENT_TYPES = [
        ("login_success", "Successful Login"),
        ("login_failed", "Failed Login"),
        ("mfa_challenge", "MFA Challenge"),
        ("mfa_success", "MFA Success"),
        ("mfa_failed", "MFA Failed"),
        ("password_change", "Password Change"),
        ("account_locked", "Account Locked"),
        ("account_unlocked", "Account Unlocked"),
        ("suspicious_activity", "Suspicious Activity"),
        ("permission_denied", "Permission Denied"),
        ("data_access", "Data Access"),
        ("api_access", "API Access"),
    ]

    SEVERITY_LEVELS = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("critical", "Critical"),
    ]

    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="security_events",
        blank=True,
        null=True,
    )
    event_type = models.CharField(max_length=50, choices=EVENT_TYPES)
    severity = models.CharField(
        max_length=20, choices=SEVERITY_LEVELS, default="medium"
    )
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True, null=True)
    platform = models.CharField(
        max_length=20, choices=PLATFORM_CHOICES, blank=True, null=True
    )
    details = models.JSONField(
        default=dict, blank=True
    )  # Additional event-specific data
    is_resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(blank=True, null=True)
    resolved_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="resolved_events",
    )
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "security_events"
        verbose_name = "Security Event"
        verbose_name_plural = "Security Events"
        ordering = ["-timestamp"]

    def __str__(self):
        user_str = self.user.email if self.user else "Anonymous"
        return f"{self.event_type} - {user_str} ({self.timestamp})"


# =============================================================================
# AUDIT AND LOGGING MODELS
# =============================================================================


class AuthenticationAudit(models.Model):
    """
    Comprehensive audit trail for authentication events
    """

    ACTION_CHOICES = [
        ("login", "Login"),
        ("logout", "Logout"),
        ("register", "Registration"),
        ("password_reset", "Password Reset"),
        ("email_verification", "Email Verification"),
        ("mfa_setup", "MFA Setup"),
        ("mfa_challenge", "MFA Challenge"),
        ("account_locked", "Account Locked"),
        ("account_unlocked", "Account Unlocked"),
        ("profile_update", "Profile Update"),
        ("role_assignment", "Role Assignment"),
        ("permission_granted", "Permission Granted"),
        ("permission_denied", "Permission Denied"),
        ("data_access", "Data Access"),
        ("data_modification", "Data Modification"),
    ]

    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="auth_audit_logs",
        blank=True,
        null=True,
    )
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    platform = models.CharField(
        max_length=20, choices=PLATFORM_CHOICES, blank=True, null=True
    )
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    success = models.BooleanField()
    details = models.JSONField(default=dict, blank=True)
    resource_accessed = models.CharField(max_length=200, blank=True, null=True)
    method = models.CharField(max_length=10, blank=True, null=True)  # HTTP method
    endpoint = models.CharField(max_length=500, blank=True, null=True)
    response_code = models.IntegerField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "authentication_audit"
        verbose_name = "Authentication Audit"
        verbose_name_plural = "Authentication Audits"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["user", "timestamp"]),
            models.Index(fields=["action", "timestamp"]),
            models.Index(fields=["platform", "timestamp"]),
            models.Index(fields=["ip_address", "timestamp"]),
        ]

    def __str__(self):
        user_str = self.user.email if self.user else "Anonymous"
        return f"{self.action} - {user_str} ({self.timestamp})"


class DataAccessLog(models.Model):
    """
    Track access to sensitive data for compliance
    """

    ACCESS_TYPES = [
        ("view", "View"),
        ("create", "Create"),
        ("update", "Update"),
        ("delete", "Delete"),
        ("export", "Export"),
        ("print", "Print"),
    ]

    DATA_TYPES = [
        ("patient_data", "Patient Data"),
        ("medical_records", "Medical Records"),
        ("prescription_data", "Prescription Data"),
        ("financial_data", "Financial Data"),
        ("personal_info", "Personal Information"),
        ("system_data", "System Data"),
    ]

    user = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="data_access_logs"
    )
    data_type = models.CharField(max_length=50, choices=DATA_TYPES)
    access_type = models.CharField(max_length=20, choices=ACCESS_TYPES)
    resource_id = models.CharField(
        max_length=100, blank=True, null=True
    )  # ID of the accessed resource
    resource_name = models.CharField(max_length=200, blank=True, null=True)
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True, null=True)
    access_reason = models.CharField(max_length=200, blank=True, null=True)
    details = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "data_access_logs"
        verbose_name = "Data Access Log"
        verbose_name_plural = "Data Access Logs"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["user", "timestamp"]),
            models.Index(fields=["data_type", "timestamp"]),
            models.Index(fields=["platform", "timestamp"]),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.access_type} {self.data_type} ({self.timestamp})"


# =============================================================================
# UTILITY FUNCTIONS AND SIGNALS
# =============================================================================


def create_platform_profile(sender, instance, created, **kwargs):
    """
    Signal to automatically create platform-specific profile when user is created
    """
    if created and instance.platform:
        # Create base profile
        UserProfile.objects.get_or_create(user=instance, platform=instance.platform)

        # Create platform-specific profile using lazy imports to avoid circular dependencies
        if instance.platform == "communities":
            from communities.models import CommunityProfile

            CommunityProfile.objects.get_or_create(user=instance)
        elif instance.platform == "professionals":
            from professionals.models import ProfessionalProfile

            ProfessionalProfile.objects.get_or_create(user=instance)
        elif instance.platform == "facilities":
            from facilities.models import FacilityProfile

            FacilityProfile.objects.get_or_create(user=instance)
        elif instance.platform == "partners":
            from partners.models import PartnerProfile

            PartnerProfile.objects.get_or_create(user=instance)
        elif instance.platform == "pharmacies":
            from pharmacies.models import PharmacyProfile

            PharmacyProfile.objects.get_or_create(user=instance)
        elif instance.platform == "patients":
            from patients.models import PatientProfile

            PatientProfile.objects.get_or_create(user=instance)


def log_security_event(sender, instance, created, **kwargs):
    """
    Signal to log security events
    """
    if created:
        SecurityEvent.objects.create(
            user=instance.user if hasattr(instance, "user") else None,
            event_type="security_event",
            ip_address=instance.ip_address if hasattr(instance, "ip_address") else None,
            details={"event": "model_created", "model": instance.__class__.__name__},
        )


# Connect signals
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender=CustomUser)
def user_post_save(sender, instance, created, **kwargs):
    if created:
        create_platform_profile(sender, instance, created, **kwargs)
