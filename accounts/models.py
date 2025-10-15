from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from phonenumber_field.modelfields import PhoneNumberField
from django.contrib.auth.models import Permission
import uuid


# Platform Choices
PLATFORM_CHOICES = [
    ('communities', 'Communities'),
    ('facilities', 'Health Facilities'),
    ('professionals', 'Individual Professionals'),
    ('partners', 'Partners'),
    ('pharmacies', 'Pharmacies'),
    ('patients', 'Patients/Users'),
]

# Verification Level Choices
VERIFICATION_LEVEL_CHOICES = [
    ('basic', 'Basic'),
    ('verified', 'Verified'),
    ('professional', 'Professional'),
    ('admin', 'Administrator'),
]

# MFA Method Choices
MFA_METHOD_CHOICES = [
    ('sms', 'SMS'),
    ('email', 'Email'),
    ('totp', 'TOTP'),
    ('disabled', 'Disabled'),
]

# Professional Role Choices
PROFESSIONAL_ROLE_CHOICES = [
    ('doctor', 'Doctor'),
    ('nurse', 'Nurse'),
    ('midwife', 'Midwife'),
    ('pharmacist', 'Pharmacist'),
    ('community_health_worker', 'Community Health Worker'),
    ('medical_assistant', 'Medical Assistant'),
    ('lab_technician', 'Lab Technician'),
    ('radiologist', 'Radiologist'),
    ('other', 'Other'),
]


class CustomUser(AbstractUser):
    """
    Enhanced User model supporting multi-platform authentication
    """
    # Basic Information
    phone_number = PhoneNumberField(blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    profile_picture = models.ImageField(upload_to='profiles/', blank=True, null=True)
    
    # Platform & Role Management
    platform = models.CharField(
        max_length=20, 
        choices=PLATFORM_CHOICES,
        default='patients'
    )
    primary_role = models.CharField(
        max_length=50,
        choices=PROFESSIONAL_ROLE_CHOICES,
        default='other'
    )
    is_verified = models.BooleanField(default=False)
    verification_level = models.CharField(
        max_length=20, 
        choices=VERIFICATION_LEVEL_CHOICES,
        default='basic'
    )
    
    # Professional Information (for healthcare workers)
    license_number = models.CharField(max_length=100, blank=True, null=True)
    license_expiry = models.DateField(blank=True, null=True)
    specializations = models.JSONField(default=list, blank=True)
    
    # Security & Compliance
    mfa_enabled = models.BooleanField(default=False)
    mfa_method = models.CharField(
        max_length=20, 
        choices=MFA_METHOD_CHOICES,
        default='disabled'
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
        db_table = 'auth_user'
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __str__(self):
        return self.email or self.username

    def is_account_locked(self):
        """Check if account is currently locked"""
        if self.account_locked_until:
            return timezone.now() < self.account_locked_until
        return False

    def lock_account(self, duration_minutes=30):
        """Lock account for specified duration"""
        self.account_locked_until = timezone.now() + timezone.timedelta(minutes=duration_minutes)
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


class Facility(models.Model):
    """
    Health facilities that users can be affiliated with
    """
    name = models.CharField(max_length=200)
    facility_code = models.CharField(max_length=50, unique=True)
    facility_type = models.CharField(max_length=100)  # Hospital, Clinic, CHPS, etc.
    address = models.TextField()
    district = models.CharField(max_length=100)
    region = models.CharField(max_length=100)
    phone_number = PhoneNumberField(blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    
    # Location
    latitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'facilities'
        verbose_name = 'Facility'
        verbose_name_plural = 'Facilities'

    def __str__(self):
        return self.name


class UserProfile(models.Model):
    """
    Platform-specific user profiles extending the base user
    """
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='profile')
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES)
    
    # Common profile fields
    bio = models.TextField(blank=True, null=True)
    location = models.CharField(max_length=200, blank=True, null=True)
    preferred_language = models.CharField(max_length=10, default='en')
    
    # Platform-specific JSON data
    profile_data = models.JSONField(default=dict, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'user_profiles'
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'

    def __str__(self):
        return f"{self.user.email} - {self.platform}"


class CommunityProfile(models.Model):
    """
    Specific profile for Community platform users
    """
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='community_profile')
    organization_name = models.CharField(max_length=200, blank=True, null=True)
    organization_type = models.CharField(max_length=100, blank=True, null=True)  # NGO, Church, CBO, etc.
    volunteer_status = models.BooleanField(default=False)
    coordinator_level = models.CharField(max_length=50, blank=True, null=True)  # Lead, Assistant, Volunteer
    areas_of_focus = models.JSONField(default=list, blank=True)  # Health areas they work in
    
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
        db_table = 'community_profiles'
        verbose_name = 'Community Profile'
        verbose_name_plural = 'Community Profiles'

    def __str__(self):
        return f"{self.user.email} - {self.organization_name}"


class ProfessionalProfile(models.Model):
    """
    Specific profile for Individual Professionals
    """
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='professional_profile')
    
    # Professional details
    practice_type = models.CharField(max_length=100)  # Private, Public, Locum, etc.
    years_of_experience = models.IntegerField(default=0)
    education_background = models.JSONField(default=list, blank=True)
    
    # License and certification
    license_number = models.CharField(max_length=100, unique=True, blank=True, null=True)
    license_issuing_body = models.CharField(max_length=100, blank=True, null=True)
    license_expiry_date = models.DateField(blank=True, null=True)
    certifications = models.JSONField(default=list, blank=True)
    
    # Availability and preferences
    availability_schedule = models.JSONField(default=dict, blank=True)
    preferred_working_hours = models.JSONField(default=dict, blank=True)
    travel_radius = models.IntegerField(default=0)  # in kilometers
    
    # Financial information
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    currency = models.CharField(max_length=3, default='GHS')
    
    # Specializations and skills
    specializations = models.JSONField(default=list, blank=True)
    languages_spoken = models.JSONField(default=list, blank=True)
    
    # References
    emergency_contact = models.CharField(max_length=200, blank=True, null=True)
    emergency_phone = PhoneNumberField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'professional_profiles'
        verbose_name = 'Professional Profile'
        verbose_name_plural = 'Professional Profiles'

    def __str__(self):
        return f"{self.user.email} - {self.user.primary_role}"

    def is_license_valid(self):
        """Check if professional license is valid"""
        if not self.license_expiry_date:
            return False
        return timezone.now().date() <= self.license_expiry_date


class FacilityProfile(models.Model):
    """
    Specific profile for Health Facility users
    """
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='facility_profile')
    facility = models.ForeignKey(Facility, on_delete=models.CASCADE, related_name='staff')
    
    # Employment details
    employee_id = models.CharField(max_length=50, blank=True, null=True)
    department = models.CharField(max_length=100, blank=True, null=True)
    position = models.CharField(max_length=100, blank=True, null=True)
    employment_type = models.CharField(max_length=50, blank=True, null=True)  # Full-time, Part-time, Contract
    hire_date = models.DateField(blank=True, null=True)
    
    # Work schedule
    shift_schedule = models.JSONField(default=dict, blank=True)
    working_hours = models.JSONField(default=dict, blank=True)
    
    # Access and permissions
    can_prescribe = models.BooleanField(default=False)  # For doctors
    can_access_patient_data = models.BooleanField(default=True)
    can_manage_inventory = models.BooleanField(default=False)
    can_schedule_appointments = models.BooleanField(default=False)
    
    # Supervisor information
    supervisor = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, blank=True, null=True, related_name='subordinates')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'facility_profiles'
        verbose_name = 'Facility Profile'
        verbose_name_plural = 'Facility Profiles'

    def __str__(self):
        return f"{self.user.email} - {self.facility.name}"


class PartnerProfile(models.Model):
    """
    Specific profile for Partner platform users
    """
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='partner_profile')
    
    # Organization details
    organization_name = models.CharField(max_length=200)
    organization_type = models.CharField(max_length=100)  # NGO, Government, Corporate, etc.
    organization_size = models.CharField(max_length=50, blank=True, null=True)
    
    # Contact information
    organization_phone = PhoneNumberField(blank=True, null=True)
    organization_email = models.EmailField(blank=True, null=True)
    organization_address = models.TextField(blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    
    # Partnership details
    partnership_type = models.CharField(max_length=100)  # Funding, Technical, Service Provider
    partnership_status = models.CharField(max_length=50, default='active')
    partnership_start_date = models.DateField(blank=True, null=True)
    partnership_end_date = models.DateField(blank=True, null=True)
    
    # API and integration access
    api_access_level = models.CharField(max_length=50, default='basic')
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
        db_table = 'partner_profiles'
        verbose_name = 'Partner Profile'
        verbose_name_plural = 'Partner Profiles'

    def __str__(self):
        return f"{self.user.email} - {self.organization_name}"


class PharmacyProfile(models.Model):
    """
    Specific profile for Pharmacy platform users
    """
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='pharmacy_profile')
    
    # Pharmacy details
    pharmacy_name = models.CharField(max_length=200)
    pharmacy_license = models.CharField(max_length=100, unique=True)
    pharmacy_type = models.CharField(max_length=100)  # Retail, Hospital, Clinic, etc.
    
    # Location
    address = models.TextField()
    district = models.CharField(max_length=100)
    region = models.CharField(max_length=100)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    
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
        db_table = 'pharmacy_profiles'
        verbose_name = 'Pharmacy Profile'
        verbose_name_plural = 'Pharmacy Profiles'

    def __str__(self):
        return f"{self.user.email} - {self.pharmacy_name}"


class PatientProfile(models.Model):
    """
    Specific profile for Patient/User platform users
    """
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='patient_profile')
    
    # Basic health information
    blood_type = models.CharField(max_length=5, blank=True, null=True)
    height = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)  # in cm
    weight = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)  # in kg
    
    # Emergency contact
    emergency_contact_name = models.CharField(max_length=200, blank=True, null=True)
    emergency_contact_phone = PhoneNumberField(blank=True, null=True)
    emergency_contact_relationship = models.CharField(max_length=100, blank=True, null=True)
    
    # Insurance and payment
    insurance_provider = models.CharField(max_length=100, blank=True, null=True)
    insurance_number = models.CharField(max_length=100, blank=True, null=True)
    preferred_payment_method = models.CharField(max_length=50, default='mobile_money')
    
    # Preferences
    preferred_language = models.CharField(max_length=10, default='en')
    preferred_consultation_type = models.CharField(max_length=50, default='in_person')
    notification_preferences = models.JSONField(default=dict, blank=True)
    
    # Health history
    medical_history = models.JSONField(default=list, blank=True)
    allergies = models.JSONField(default=list, blank=True)
    current_medications = models.JSONField(default=list, blank=True)
    
    # Location
    home_address = models.TextField(blank=True, null=True)
    work_address = models.TextField(blank=True, null=True)
    preferred_pharmacy = models.ForeignKey('PharmacyProfile', on_delete=models.SET_NULL, blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'patient_profiles'
        verbose_name = 'Patient Profile'
        verbose_name_plural = 'Patient Profiles'

    def __str__(self):
        return f"{self.user.email} - Patient"

    def calculate_bmi(self):
        """Calculate BMI if height and weight are available"""
        if self.height and self.weight:
            height_m = float(self.height) / 100  # Convert cm to m
            weight_kg = float(self.weight)
            return round(weight_kg / (height_m ** 2), 2)
        return None


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
        db_table = 'roles'
        verbose_name = 'Role'
        verbose_name_plural = 'Roles'
        unique_together = ['name', 'platform']

    def __str__(self):
        return f"{self.name} ({self.platform})"


class UserRole(models.Model):
    """
    User role assignments with facility context for facility-specific roles
    """
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='user_roles')
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='user_assignments')
    facility = models.ForeignKey(Facility, on_delete=models.CASCADE, blank=True, null=True, related_name='role_assignments')
    assigned_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, blank=True, null=True, related_name='assigned_roles')
    assigned_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'user_roles'
        verbose_name = 'User Role'
        verbose_name_plural = 'User Roles'
        unique_together = ['user', 'role', 'facility']

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
        ('sms', 'SMS'),
        ('email', 'Email'),
        ('totp', 'TOTP'),
        ('backup_codes', 'Backup Codes'),
    ]

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='mfa_devices')
    device_type = models.CharField(max_length=20, choices=DEVICE_TYPES)
    device_id = models.CharField(max_length=100)  # Phone number, email, or TOTP secret
    device_name = models.CharField(max_length=100, blank=True, null=True)  # User-friendly name
    is_verified = models.BooleanField(default=False)
    is_primary = models.BooleanField(default=False)
    last_used = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'mfa_devices'
        verbose_name = 'MFA Device'
        verbose_name_plural = 'MFA Devices'
        unique_together = ['user', 'device_id']

    def __str__(self):
        return f"{self.user.email} - {self.device_type} ({self.device_name or self.device_id})"


class LoginSession(models.Model):
    """
    Track active login sessions for security monitoring
    """
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='login_sessions')
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
        db_table = 'login_sessions'
        verbose_name = 'Login Session'
        verbose_name_plural = 'Login Sessions'

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
        ('login_success', 'Successful Login'),
        ('login_failed', 'Failed Login'),
        ('mfa_challenge', 'MFA Challenge'),
        ('mfa_success', 'MFA Success'),
        ('mfa_failed', 'MFA Failed'),
        ('password_change', 'Password Change'),
        ('account_locked', 'Account Locked'),
        ('account_unlocked', 'Account Unlocked'),
        ('suspicious_activity', 'Suspicious Activity'),
        ('permission_denied', 'Permission Denied'),
        ('data_access', 'Data Access'),
        ('api_access', 'API Access'),
    ]

    SEVERITY_LEVELS = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='security_events', blank=True, null=True)
    event_type = models.CharField(max_length=50, choices=EVENT_TYPES)
    severity = models.CharField(max_length=20, choices=SEVERITY_LEVELS, default='medium')
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True, null=True)
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES, blank=True, null=True)
    details = models.JSONField(default=dict, blank=True)  # Additional event-specific data
    is_resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(blank=True, null=True)
    resolved_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, blank=True, null=True, related_name='resolved_events')
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'security_events'
        verbose_name = 'Security Event'
        verbose_name_plural = 'Security Events'
        ordering = ['-timestamp']

    def __str__(self):
        user_str = self.user.email if self.user else 'Anonymous'
        return f"{self.event_type} - {user_str} ({self.timestamp})"


# =============================================================================
# AUDIT AND LOGGING MODELS
# =============================================================================

class AuthenticationAudit(models.Model):
    """
    Comprehensive audit trail for authentication events
    """
    ACTION_CHOICES = [
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('register', 'Registration'),
        ('password_reset', 'Password Reset'),
        ('email_verification', 'Email Verification'),
        ('mfa_setup', 'MFA Setup'),
        ('mfa_challenge', 'MFA Challenge'),
        ('account_locked', 'Account Locked'),
        ('account_unlocked', 'Account Unlocked'),
        ('profile_update', 'Profile Update'),
        ('role_assignment', 'Role Assignment'),
        ('permission_granted', 'Permission Granted'),
        ('permission_denied', 'Permission Denied'),
        ('data_access', 'Data Access'),
        ('data_modification', 'Data Modification'),
    ]

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='auth_audit_logs', blank=True, null=True)
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES, blank=True, null=True)
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
        db_table = 'authentication_audit'
        verbose_name = 'Authentication Audit'
        verbose_name_plural = 'Authentication Audits'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['action', 'timestamp']),
            models.Index(fields=['platform', 'timestamp']),
            models.Index(fields=['ip_address', 'timestamp']),
        ]

    def __str__(self):
        user_str = self.user.email if self.user else 'Anonymous'
        return f"{self.action} - {user_str} ({self.timestamp})"


class DataAccessLog(models.Model):
    """
    Track access to sensitive data for compliance
    """
    ACCESS_TYPES = [
        ('view', 'View'),
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('export', 'Export'),
        ('print', 'Print'),
    ]

    DATA_TYPES = [
        ('patient_data', 'Patient Data'),
        ('medical_records', 'Medical Records'),
        ('prescription_data', 'Prescription Data'),
        ('financial_data', 'Financial Data'),
        ('personal_info', 'Personal Information'),
        ('system_data', 'System Data'),
    ]

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='data_access_logs')
    data_type = models.CharField(max_length=50, choices=DATA_TYPES)
    access_type = models.CharField(max_length=20, choices=ACCESS_TYPES)
    resource_id = models.CharField(max_length=100, blank=True, null=True)  # ID of the accessed resource
    resource_name = models.CharField(max_length=200, blank=True, null=True)
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True, null=True)
    access_reason = models.CharField(max_length=200, blank=True, null=True)
    details = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'data_access_logs'
        verbose_name = 'Data Access Log'
        verbose_name_plural = 'Data Access Logs'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['data_type', 'timestamp']),
            models.Index(fields=['platform', 'timestamp']),
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
        UserProfile.objects.get_or_create(
            user=instance,
            platform=instance.platform
        )
        
        # Create platform-specific profile
        if instance.platform == 'communities':
            CommunityProfile.objects.get_or_create(user=instance)
        elif instance.platform == 'professionals':
            ProfessionalProfile.objects.get_or_create(user=instance)
        elif instance.platform == 'facilities':
            FacilityProfile.objects.get_or_create(user=instance)
        elif instance.platform == 'partners':
            PartnerProfile.objects.get_or_create(user=instance)
        elif instance.platform == 'pharmacies':
            PharmacyProfile.objects.get_or_create(user=instance)
        elif instance.platform == 'patients':
            PatientProfile.objects.get_or_create(user=instance)


def log_security_event(sender, instance, created, **kwargs):
    """
    Signal to log security events
    """
    if created:
        SecurityEvent.objects.create(
            user=instance.user if hasattr(instance, 'user') else None,
            event_type='security_event',
            ip_address=instance.ip_address if hasattr(instance, 'ip_address') else None,
            details={'event': 'model_created', 'model': instance.__class__.__name__}
        )


# Connect signals
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=CustomUser)
def user_post_save(sender, instance, created, **kwargs):
    if created:
        create_platform_profile(sender, instance, created, **kwargs)


# ====================
# General User & Service Request Models
# ====================

class GuestUser(models.Model):
    """
    Model for non-registered users who interact with the platform
    Can be converted to a full CustomUser account later
    """
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    
    # Location information
    location = models.CharField(max_length=255, blank=True, null=True)
    district = models.CharField(max_length=100, blank=True, null=True)
    region = models.CharField(max_length=100, blank=True, null=True)
    
    # Tracking
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_activity = models.DateTimeField(auto_now=True)
    
    # Conversion tracking
    converted_to_user = models.ForeignKey(
        CustomUser, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='converted_from_guest'
    )
    is_converted = models.BooleanField(default=False)
    
    # Preferences
    newsletter_subscription = models.BooleanField(default=False)
    preferred_language = models.CharField(max_length=10, default='en')
    
    class Meta:
        verbose_name = "Guest User"
        verbose_name_plural = "Guest Users"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['phone_number']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.email})"


class LocumRequest(models.Model):
    """
    Model for locum tenens (temporary healthcare professional) requests
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('reviewing', 'Under Review'),
        ('matched', 'Professional Matched'),
        ('accepted', 'Accepted by Professional'),
        ('confirmed', 'Confirmed'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired'),
    ]
    
    URGENCY_CHOICES = [
        ('low', 'Low - 2+ weeks'),
        ('medium', 'Medium - 1 week'),
        ('high', 'High - 1-3 days'),
        ('urgent', 'Urgent - Within 24 hours'),
    ]
    
    # Requester information
    requester_user = models.ForeignKey(
        CustomUser, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='locum_requests_as_user'
    )
    requester_guest = models.ForeignKey(
        GuestUser, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='locum_requests'
    )
    
    # Facility requesting the locum
    facility = models.ForeignKey(
        Facility, 
        on_delete=models.CASCADE,
        related_name='locum_requests',
        null=True,
        blank=True
    )
    facility_name = models.CharField(max_length=255, help_text="If facility not in system")
    facility_address = models.TextField(blank=True)
    
    # Position details
    position_title = models.CharField(max_length=255)
    specialty_required = models.CharField(max_length=255)
    department = models.CharField(max_length=255, blank=True)
    
    # Duration and timing
    start_date = models.DateField()
    end_date = models.DateField()
    duration_days = models.IntegerField(editable=False)
    shift_type = models.CharField(
        max_length=50,
        choices=[
            ('day', 'Day Shift'),
            ('night', 'Night Shift'),
            ('rotating', 'Rotating'),
            ('on_call', 'On-Call'),
        ],
        default='day'
    )
    hours_per_week = models.DecimalField(max_digits=5, decimal_places=2)
    
    # Requirements
    minimum_experience_years = models.IntegerField(default=0)
    license_requirements = models.TextField(blank=True)
    certifications_required = models.JSONField(default=list, blank=True)
    skills_required = models.JSONField(default=list, blank=True)
    
    # Compensation
    offered_rate = models.DecimalField(max_digits=10, decimal_places=2, help_text="Rate per hour/day")
    rate_type = models.CharField(
        max_length=20,
        choices=[('hourly', 'Hourly'), ('daily', 'Daily'), ('weekly', 'Weekly')],
        default='daily'
    )
    accommodation_provided = models.BooleanField(default=False)
    transportation_provided = models.BooleanField(default=False)
    
    # Additional details
    urgency = models.CharField(max_length=20, choices=URGENCY_CHOICES, default='medium')
    description = models.TextField()
    special_requirements = models.TextField(blank=True)
    
    # Status and matching
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    matched_professional = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='matched_locum_requests'
    )
    
    # Contact information
    contact_person = models.CharField(max_length=255)
    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=20)
    
    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Locum Request"
        verbose_name_plural = "Locum Requests"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['start_date', 'end_date']),
            models.Index(fields=['specialty_required']),
            models.Index(fields=['urgency']),
        ]
    
    def save(self, *args, **kwargs):
        # Calculate duration
        if self.start_date and self.end_date:
            self.duration_days = (self.end_date - self.start_date).days
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.position_title} at {self.facility_name} ({self.start_date})"
    
    @property
    def is_expired(self):
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False


class PrescriptionRequest(models.Model):
    """
    Model for prescription requests from general users
    """
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('dispensed', 'Dispensed'),
        ('rejected', 'Rejected'),
        ('expired', 'Expired'),
    ]
    
    # Requester
    requester_user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='prescription_requests_as_user'
    )
    requester_guest = models.ForeignKey(
        GuestUser,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='prescription_requests'
    )
    
    # Prescription details
    prescription_image = models.ImageField(upload_to='prescriptions/', blank=True, null=True)
    prescription_number = models.CharField(max_length=100, unique=True, blank=True)
    medication_name = models.CharField(max_length=255)
    dosage = models.CharField(max_length=100)
    quantity = models.IntegerField()
    refills = models.IntegerField(default=0)
    
    # Medical info
    prescribing_doctor = models.CharField(max_length=255, blank=True)
    diagnosis = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    
    # Pharmacy selection
    preferred_pharmacy = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='prescription_requests',
        limit_choices_to={'platform': 'pharmacies'}
    )
    delivery_required = models.BooleanField(default=False)
    delivery_address = models.TextField(blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    approved_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_prescriptions'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Prescription Request"
        verbose_name_plural = "Prescription Requests"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['prescription_number']),
        ]
    
    def __str__(self):
        return f"{self.medication_name} - {self.get_status_display()}"


class AppointmentRequest(models.Model):
    """
    Model for appointment booking requests
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('rescheduled', 'Rescheduled'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('no_show', 'No Show'),
    ]
    
    APPOINTMENT_TYPE_CHOICES = [
        ('consultation', 'General Consultation'),
        ('follow_up', 'Follow-up'),
        ('emergency', 'Emergency'),
        ('specialist', 'Specialist Consultation'),
        ('lab_test', 'Lab Test'),
        ('imaging', 'Imaging/Radiology'),
        ('vaccination', 'Vaccination'),
        ('health_screening', 'Health Screening'),
    ]
    
    # Requester
    requester_user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='appointment_requests_as_user'
    )
    requester_guest = models.ForeignKey(
        GuestUser,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='appointment_requests'
    )
    
    # Appointment details
    appointment_type = models.CharField(max_length=50, choices=APPOINTMENT_TYPE_CHOICES)
    preferred_date = models.DateField()
    preferred_time = models.TimeField()
    alternative_dates = models.JSONField(default=list, blank=True)
    
    # Provider selection
    facility = models.ForeignKey(
        Facility,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='appointment_requests'
    )
    preferred_professional = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='appointment_requests',
        limit_choices_to={'platform': 'professionals'}
    )
    
    # Patient information
    patient_name = models.CharField(max_length=255)
    patient_age = models.IntegerField()
    patient_gender = models.CharField(max_length=20)
    patient_phone = models.CharField(max_length=20)
    patient_email = models.EmailField()
    
    # Medical details
    reason_for_visit = models.TextField()
    symptoms = models.TextField(blank=True)
    medical_history = models.TextField(blank=True)
    current_medications = models.TextField(blank=True)
    allergies = models.TextField(blank=True)
    
    # Insurance
    has_insurance = models.BooleanField(default=False)
    insurance_provider = models.CharField(max_length=255, blank=True)
    insurance_number = models.CharField(max_length=100, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    confirmed_date = models.DateField(null=True, blank=True)
    confirmed_time = models.TimeField(null=True, blank=True)
    confirmation_code = models.CharField(max_length=50, unique=True, blank=True)
    
    # Notes
    notes = models.TextField(blank=True)
    admin_notes = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Appointment Request"
        verbose_name_plural = "Appointment Requests"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'preferred_date']),
            models.Index(fields=['confirmation_code']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.appointment_type} - {self.patient_name} on {self.preferred_date}"


class EventRegistration(models.Model):
    """
    Model for health event registrations (health camps, screenings, workshops)
    """
    STATUS_CHOICES = [
        ('registered', 'Registered'),
        ('confirmed', 'Confirmed'),
        ('attended', 'Attended'),
        ('cancelled', 'Cancelled'),
        ('no_show', 'No Show'),
    ]
    
    # Registrant
    registrant_user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='event_registrations_as_user'
    )
    registrant_guest = models.ForeignKey(
        GuestUser,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='event_registrations'
    )
    
    # Event details (in real implementation, you'd have a separate Event model)
    event_name = models.CharField(max_length=255)
    event_date = models.DateField()
    event_time = models.TimeField()
    event_location = models.CharField(max_length=255)
    event_type = models.CharField(
        max_length=50,
        choices=[
            ('health_camp', 'Health Camp'),
            ('screening', 'Health Screening'),
            ('workshop', 'Workshop'),
            ('seminar', 'Seminar'),
            ('vaccination_drive', 'Vaccination Drive'),
        ]
    )
    
    # Organizer
    organized_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='organized_events'
    )
    
    # Participant details
    participant_name = models.CharField(max_length=255)
    participant_email = models.EmailField()
    participant_phone = models.CharField(max_length=20)
    participant_age = models.IntegerField(null=True, blank=True)
    
    # Additional info
    number_of_attendees = models.IntegerField(default=1)
    special_requirements = models.TextField(blank=True)
    dietary_restrictions = models.TextField(blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='registered')
    registration_code = models.CharField(max_length=50, unique=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Event Registration"
        verbose_name_plural = "Event Registrations"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'event_date']),
            models.Index(fields=['registration_code']),
        ]
    
    def __str__(self):
        return f"{self.participant_name} - {self.event_name} ({self.event_date})"
    
    def save(self, *args, **kwargs):
        if not self.registration_code:
            import uuid
            self.registration_code = f"REG{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)