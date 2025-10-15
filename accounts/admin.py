from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from unfold.admin import ModelAdmin

from .forms import CustomUserCreationForm, CustomUserChangeForm
from .models import (
    CustomUser, Facility, UserProfile, CommunityProfile, ProfessionalProfile,
    FacilityProfile, PartnerProfile, PharmacyProfile, PatientProfile,
    Role, UserRole, MFADevice, LoginSession, SecurityEvent,
    AuthenticationAudit, DataAccessLog, GuestUser, LocumRequest,
    PrescriptionRequest, AppointmentRequest, EventRegistration
)


@admin.register(CustomUser)
class CustomUserAdmin(ModelAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = CustomUser
    
    list_display = [
        "email",
        "username",
        "platform",
        "primary_role",
        "verification_level",
        "is_verified",
        "mfa_enabled",
        "is_active",
        "is_staff",
        "created_at",
    ]
    
    list_filter = [
        "platform",
        "primary_role",
        "verification_level",
        "is_verified",
        "mfa_enabled",
        "is_active",
        "is_staff",
        "created_at",
    ]
    
    search_fields = [
        "email",
        "username",
        "first_name",
        "last_name",
        "phone_number",
    ]
    
    ordering = ["-created_at"]
    
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Personal info", {
            "fields": (
                "first_name", "last_name", "email", "phone_number", 
                "date_of_birth", "profile_picture"
            )
        }),
        ("Platform & Role", {
            "fields": (
                "platform", "primary_role", "verification_level", "is_verified"
            )
        }),
        ("Professional Info", {
            "fields": (
                "license_number", "license_expiry", "specializations"
            )
        }),
        ("Security", {
            "fields": (
                "mfa_enabled", "mfa_method", "last_login_ip", 
                "login_attempts", "account_locked_until"
            )
        }),
        ("Permissions", {
            "fields": (
                "is_active", "is_staff", "is_superuser",
                "groups", "user_permissions"
            )
        }),
        ("Important dates", {
            "fields": (
                "last_login", "created_at", "updated_at", "last_activity"
            )
        }),
    )
    
    readonly_fields = ["created_at", "updated_at", "last_activity", "last_login"]
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('profile')
    
    def get_form(self, request, obj=None, **kwargs):
        """
        Use custom form for user creation and editing
        """
        defaults = {}
        if obj is None:
            defaults['form'] = self.add_form
        else:
            defaults['form'] = self.form
        defaults.update(kwargs)
        return super().get_form(request, obj, **defaults)
    
    def save_model(self, request, obj, form, change):
        """
        Handle password hashing and user creation
        """
        if not change:  # Creating new user
            obj.set_password(form.cleaned_data.get('password'))
        super().save_model(request, obj, form, change)


@admin.register(Facility)
class FacilityAdmin(ModelAdmin):
    list_display = [
        "name",
        "facility_code",
        "facility_type",
        "district",
        "region",
        "is_active",
        "created_at",
    ]
    
    list_filter = [
        "facility_type",
        "district",
        "region",
        "is_active",
        "created_at",
    ]
    
    search_fields = [
        "name",
        "facility_code",
        "district",
        "region",
    ]
    
    ordering = ["name"]


@admin.register(UserProfile)
class UserProfileAdmin(ModelAdmin):
    list_display = [
        "user",
        "platform",
        "preferred_language",
        "created_at",
    ]
    
    list_filter = [
        "platform",
        "preferred_language",
        "created_at",
    ]
    
    search_fields = [
        "user__email",
        "user__username",
        "location",
    ]


@admin.register(CommunityProfile)
class CommunityProfileAdmin(ModelAdmin):
    list_display = [
        "user",
        "organization_name",
        "organization_type",
        "coordinator_level",
        "volunteer_status",
        "created_at",
    ]
    
    list_filter = [
        "organization_type",
        "coordinator_level",
        "volunteer_status",
        "created_at",
    ]
    
    search_fields = [
        "user__email",
        "organization_name",
        "organization_type",
    ]


@admin.register(ProfessionalProfile)
class ProfessionalProfileAdmin(ModelAdmin):
    list_display = [
        "user",
        "practice_type",
        "years_of_experience",
        "license_number",
        "license_expiry_date",
        "is_license_valid",
        "created_at",
    ]
    
    list_filter = [
        "practice_type",
        "years_of_experience",
        "license_issuing_body",
        "created_at",
    ]
    
    search_fields = [
        "user__email",
        "license_number",
        "practice_type",
    ]
    
    readonly_fields = ["is_license_valid"]


@admin.register(FacilityProfile)
class FacilityProfileAdmin(ModelAdmin):
    list_display = [
        "user",
        "facility",
        "department",
        "position",
        "employment_type",
        "can_prescribe",
        "can_access_patient_data",
        "created_at",
    ]
    
    list_filter = [
        "facility",
        "department",
        "position",
        "employment_type",
        "can_prescribe",
        "can_access_patient_data",
        "created_at",
    ]
    
    search_fields = [
        "user__email",
        "facility__name",
        "employee_id",
        "position",
    ]


@admin.register(PartnerProfile)
class PartnerProfileAdmin(ModelAdmin):
    list_display = [
        "user",
        "organization_name",
        "organization_type",
        "partnership_type",
        "partnership_status",
        "api_access_level",
        "created_at",
    ]
    
    list_filter = [
        "organization_type",
        "partnership_type",
        "partnership_status",
        "api_access_level",
        "created_at",
    ]
    
    search_fields = [
        "user__email",
        "organization_name",
        "organization_type",
    ]


@admin.register(PharmacyProfile)
class PharmacyProfileAdmin(ModelAdmin):
    list_display = [
        "user",
        "pharmacy_name",
        "pharmacy_type",
        "district",
        "region",
        "delivery_available",
        "created_at",
    ]
    
    list_filter = [
        "pharmacy_type",
        "district",
        "region",
        "delivery_available",
        "created_at",
    ]
    
    search_fields = [
        "user__email",
        "pharmacy_name",
        "pharmacy_license",
        "district",
        "region",
    ]


@admin.register(PatientProfile)
class PatientProfileAdmin(ModelAdmin):
    list_display = [
        "user",
        "blood_type",
        "preferred_consultation_type",
        "preferred_payment_method",
        "preferred_pharmacy",
        "created_at",
    ]
    
    list_filter = [
        "blood_type",
        "preferred_consultation_type",
        "preferred_payment_method",
        "created_at",
    ]
    
    search_fields = [
        "user__email",
        "emergency_contact_name",
        "insurance_provider",
    ]


@admin.register(Role)
class RoleAdmin(ModelAdmin):
    list_display = [
        "name",
        "platform",
        "is_active",
        "created_at",
    ]
    
    list_filter = [
        "platform",
        "is_active",
        "created_at",
    ]
    
    search_fields = [
        "name",
        "platform",
        "description",
    ]


@admin.register(UserRole)
class UserRoleAdmin(ModelAdmin):
    list_display = [
        "user",
        "role",
        "facility",
        "is_active",
        "assigned_at",
        "expires_at",
        "is_expired",
    ]
    
    list_filter = [
        "role__platform",
        "is_active",
        "assigned_at",
        "expires_at",
    ]
    
    search_fields = [
        "user__email",
        "role__name",
        "facility__name",
    ]
    
    readonly_fields = ["is_expired"]


@admin.register(MFADevice)
class MFADeviceAdmin(ModelAdmin):
    list_display = [
        "user",
        "device_type",
        "device_name",
        "device_id_masked",
        "is_verified",
        "is_primary",
        "last_used",
        "created_at",
    ]
    
    list_filter = [
        "device_type",
        "is_verified",
        "is_primary",
        "created_at",
    ]
    
    search_fields = [
        "user__email",
        "device_name",
        "device_id",
    ]
    
    readonly_fields = ["device_id_masked"]
    
    def device_id_masked(self, obj):
        """Mask sensitive device ID information"""
        if obj.device_type in ['sms', 'email']:
            device_id = str(obj.device_id)
            if len(device_id) > 4:
                return f"{device_id[:2]}****{device_id[-2:]}"
        return obj.device_id
    device_id_masked.short_description = "Device ID"


@admin.register(LoginSession)
class LoginSessionAdmin(ModelAdmin):
    list_display = [
        "user",
        "ip_address",
        "is_active",
        "created_at",
        "expires_at",
        "is_expired",
    ]
    
    list_filter = [
        "is_active",
        "created_at",
        "expires_at",
    ]
    
    search_fields = [
        "user__email",
        "ip_address",
        "session_token",
    ]
    
    readonly_fields = ["session_token", "refresh_token", "is_expired"]


@admin.register(SecurityEvent)
class SecurityEventAdmin(ModelAdmin):
    list_display = [
        "event_type",
        "user",
        "severity",
        "ip_address",
        "platform",
        "is_resolved",
        "timestamp",
    ]
    
    list_filter = [
        "event_type",
        "severity",
        "platform",
        "is_resolved",
        "timestamp",
    ]
    
    search_fields = [
        "user__email",
        "ip_address",
        "event_type",
    ]
    
    readonly_fields = ["timestamp"]
    ordering = ["-timestamp"]


@admin.register(AuthenticationAudit)
class AuthenticationAuditAdmin(ModelAdmin):
    list_display = [
        "action",
        "user",
        "platform",
        "success",
        "ip_address",
        "response_code",
        "timestamp",
    ]
    
    list_filter = [
        "action",
        "platform",
        "success",
        "response_code",
        "timestamp",
    ]
    
    search_fields = [
        "user__email",
        "ip_address",
        "action",
        "endpoint",
    ]
    
    readonly_fields = ["timestamp"]
    ordering = ["-timestamp"]


@admin.register(DataAccessLog)
class DataAccessLogAdmin(ModelAdmin):
    list_display = [
        "user",
        "data_type",
        "access_type",
        "resource_name",
        "platform",
        "ip_address",
        "timestamp",
    ]
    
    list_filter = [
        "data_type",
        "access_type",
        "platform",
        "timestamp",
    ]
    
    search_fields = [
        "user__email",
        "data_type",
        "resource_name",
        "ip_address",
    ]
    
    readonly_fields = ["timestamp"]
    ordering = ["-timestamp"]


# ====================
# General User & Service Request Admin
# ====================

@admin.register(GuestUser)
class GuestUserAdmin(ModelAdmin):
    list_display = [
        "email",
        "first_name",
        "last_name",
        "phone_number",
        "is_converted",
        "created_at",
    ]
    
    list_filter = [
        "is_converted",
        "newsletter_subscription",
        "preferred_language",
        "region",
        "district",
        "created_at",
    ]
    
    search_fields = [
        "email",
        "first_name",
        "last_name",
        "phone_number",
    ]
    
    readonly_fields = ["created_at", "updated_at", "last_activity"]
    ordering = ["-created_at"]


@admin.register(LocumRequest)
class LocumRequestAdmin(ModelAdmin):
    list_display = [
        "position_title",
        "facility_name",
        "specialty_required",
        "start_date",
        "end_date",
        "status",
        "urgency",
        "created_at",
    ]
    
    list_filter = [
        "status",
        "urgency",
        "shift_type",
        "rate_type",
        "created_at",
    ]
    
    search_fields = [
        "position_title",
        "facility_name",
        "specialty_required",
        "contact_person",
        "contact_email",
    ]
    
    readonly_fields = ["duration_days", "created_at", "updated_at"]
    ordering = ["-created_at"]


@admin.register(PrescriptionRequest)
class PrescriptionRequestAdmin(ModelAdmin):
    list_display = [
        "medication_name",
        "dosage",
        "quantity",
        "status",
        "delivery_required",
        "created_at",
    ]
    
    list_filter = [
        "status",
        "delivery_required",
        "created_at",
    ]
    
    search_fields = [
        "medication_name",
        "prescription_number",
        "prescribing_doctor",
    ]
    
    readonly_fields = ["created_at", "updated_at"]
    ordering = ["-created_at"]


@admin.register(AppointmentRequest)
class AppointmentRequestAdmin(ModelAdmin):
    list_display = [
        "patient_name",
        "appointment_type",
        "preferred_date",
        "preferred_time",
        "status",
        "facility",
        "created_at",
    ]
    
    list_filter = [
        "status",
        "appointment_type",
        "has_insurance",
        "preferred_date",
        "created_at",
    ]
    
    search_fields = [
        "patient_name",
        "patient_email",
        "patient_phone",
        "confirmation_code",
    ]
    
    readonly_fields = ["created_at", "updated_at"]
    ordering = ["-created_at"]


@admin.register(EventRegistration)
class EventRegistrationAdmin(ModelAdmin):
    list_display = [
        "participant_name",
        "event_name",
        "event_type",
        "event_date",
        "status",
        "number_of_attendees",
        "registration_code",
        "created_at",
    ]
    
    list_filter = [
        "status",
        "event_type",
        "event_date",
        "created_at",
    ]
    
    search_fields = [
        "participant_name",
        "participant_email",
        "participant_phone",
        "event_name",
        "registration_code",
    ]
    
    readonly_fields = ["registration_code", "created_at", "updated_at"]
    ordering = ["-created_at"]
