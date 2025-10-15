from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from unfold.admin import ModelAdmin

from .forms import CustomUserCreationForm, CustomUserChangeForm
from .models import (
    CustomUser, UserProfile,
    Role, UserRole, MFADevice, LoginSession, SecurityEvent,
    AuthenticationAudit, DataAccessLog
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


