from rest_framework import serializers
from .models import (
    CustomUser,
    UserProfile,
    Role,
    UserRole,
    MFADevice,
    LoginSession,
    SecurityEvent,
    AuthenticationAudit,
    DataAccessLog,
)
from dj_rest_auth.serializers import LoginSerializer
from datetime import datetime, timedelta
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist
from helpers import exceptions
from helpers.functions import generate_otp
from django.db.models import Q
from django.http import HttpRequest
from loguru import logger
from phonenumber_field.serializerfields import PhoneNumberField


# SIGN UP FLOW
class ValidateEmailSerializer(serializers.Serializer):
    """
    Serializer for validating email
    """

    email = serializers.EmailField()

    def validate_email(self, value):
        if CustomUser.objects.filter(email=value).exists():
            raise exceptions.EmailAlreadyInUseException()
        return value


class ValidatePhoneNumberSerializer(serializers.Serializer):
    """
    Serializer for validating phone number
    """

    phone_number = PhoneNumberField()

    def validate_phone_number(self, value):
        if CustomUser.objects.filter(phone_number=value).exists():
            raise exceptions.PhoneNumberAlreadyInUseException()
        return value


class ValidateEmailAndPhoneNumberSerializer(serializers.Serializer):
    """
    Serializer for validating email and phone number
    """

    email = serializers.EmailField()
    phone_number = PhoneNumberField()


class VerifyEmailOTPSerializer(serializers.Serializer):
    """
    Serializer for verifying email OTP
    """

    email = serializers.EmailField()
    otp = serializers.CharField()


class VerifyPhoneNumberOTPSerializer(serializers.Serializer):
    """
    Serializer for verifying phone number OTP
    """

    phone_number = PhoneNumberField()
    otp = serializers.CharField()


# USER SECTION SERIALIZER
class AccountProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for user account
    """

    # other profiles
    profiles = serializers.SerializerMethodField()

    def get_profiles(self, obj):
        profiles = []
        if hasattr(obj, "community_profile"):
            profiles.append(
                {
                    "type": "community_profile",
                    "id": obj.community_profile.id,
                }
            )
        if hasattr(obj, "professional_profile"):
            profiles.append(
                {
                    "type": "professional_profile",
                    "id": obj.professional_profile.id,
                }
            )
        if hasattr(obj, "facility_profile"):
            profiles.append(
                {
                    "type": "facility_profile",
                    "id": obj.facility_profile.id,
                }
            )
        if hasattr(obj, "partner_profile"):
            profiles.append(
                {
                    "type": "partner_profile",
                    "id": obj.partner_profile.id,
                }
            )
        if hasattr(obj, "pharmacy_profile"):
            profiles.append(
                {
                    "type": "pharmacy_profile",
                    "id": obj.pharmacy_profile.id,
                }
            )
        if hasattr(obj, "patient_profile"):
            profiles.append(
                {
                    "type": "patient_profile",
                    "id": obj.patient_profile.id,
                }
            )
        return profiles

    class Meta:
        model = CustomUser
        fields = [
            "email",
            "first_name",
            "last_name",
            "phone_number",
            "profiles",
            "default_profile",
            "is_verified",
            "mfa_enabled",
            "mfa_method",
            "is_active",
            "is_account_locked",
        ]


class SetDefaultProfileSerializer(serializers.Serializer):
    """
    Serializer for setting default profile
    """

    profile_id = serializers.UUIDField()



class UserCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for user creation with password handling
    """

    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = CustomUser
        fields = [
            "username",
            "email",
            "password",
            "password_confirm",
            "first_name",
            "last_name",
            "phone_number",
            "date_of_birth",
            "id_type",
            "id_number",
        ]
        extra_kwargs = {
            "password": {"write_only": True},
        }

    def validate(self, attrs):
        """Validate password confirmation"""
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError("Passwords don't match.")
        return attrs

    def create(self, validated_data):
        """Create user with hashed password"""
        validated_data.pop("password_confirm")
        password = validated_data.pop("password")
        user = CustomUser.objects.create(**validated_data)
        user.set_password(password)
        user.save()
        return user


class UserSerializer(serializers.ModelSerializer):
    """
    Enhanced User serializer with platform support
    """

    is_account_locked = serializers.BooleanField(read_only=True)

    class Meta:
        model = CustomUser
        fields = (
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "phone_number",
            "is_verified",
            "mfa_enabled",
            "mfa_method",
            "is_active",
            "is_account_locked",
            "last_activity",
        )
        read_only_fields = (
            "id",
            "is_active",
            "is_staff",
            "is_account_locked",
            "created_at",
            "updated_at",
            "last_activity",
        )


class UserCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for user creation with platform-specific validation
    """

    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = CustomUser
        fields = (
            "username",
            "email",
            "first_name",
            "last_name",
            "phone_number",
            "date_of_birth",
            "password",
            "password_confirm",
        )

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError("Passwords don't match")
        return attrs

    def create(self, validated_data):
        validated_data.pop("password_confirm")
        password = validated_data.pop("password")
        user = CustomUser.objects.create_user(**validated_data)
        user.set_password(password)
        user.save()
        return user


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Base user profile serializer
    """

    user = UserSerializer(read_only=True)

    class Meta:
        model = UserProfile
        fields = (
            "id",
            "user",
            "bio",
            "location",
            "preferred_language",
            "profile_data",
            "created_at",
            "updated_at",
        )


class CreateOrganizationUserSerializer(serializers.Serializer):
    """
    Serializer for creating an organization user
    """

    organization_email = serializers.EmailField()
    organization_phone = PhoneNumberField()

    # organization details
    organization_name = serializers.CharField()
    organization_type = serializers.CharField()
    registration_number = serializers.CharField()

    # security
    password = serializers.CharField(write_only=True, min_length=8)


class RoleSerializer(serializers.ModelSerializer):
    """
    Role serializer
    """

    user_count = serializers.SerializerMethodField()

    class Meta:
        model = Role
        fields = (
            "id",
            "name",
            "description",
            "permissions",
            "is_active",
            "user_count",
            "created_at",
            "updated_at",
        )

    def get_user_count(self, obj):
        return obj.user_assignments.filter(is_active=True).count()


class UserRoleSerializer(serializers.ModelSerializer):
    """
    User role assignment serializer
    """

    user = UserSerializer(read_only=True)
    role = RoleSerializer(read_only=True)
    facility_name = serializers.SerializerMethodField()
    assigned_by_name = serializers.CharField(
        source="assigned_by.get_full_name", read_only=True
    )
    is_expired = serializers.BooleanField(read_only=True)

    class Meta:
        model = UserRole
        fields = (
            "id",
            "user",
            "role",
            "facility",
            "facility_name",
            "assigned_by",
            "assigned_by_name",
            "assigned_at",
            "expires_at",
            "is_active",
            "is_expired",
            "notes",
        )

    def get_facility_name(self, obj):
        if obj.facility:
            return obj.facility.name
        return None


class MFADeviceSerializer(serializers.ModelSerializer):
    """
    MFA device serializer
    """

    device_type_display = serializers.CharField(
        source="get_device_type_display", read_only=True
    )
    device_id_masked = serializers.SerializerMethodField()

    class Meta:
        model = MFADevice
        fields = (
            "id",
            "device_type",
            "device_type_display",
            "device_id",
            "device_id_masked",
            "device_name",
            "is_verified",
            "is_primary",
            "last_used",
            "created_at",
            "updated_at",
        )

    def get_device_id_masked(self, obj):
        """Mask sensitive device ID information"""
        if obj.device_type in ["sms", "email"]:
            device_id = str(obj.device_id)
            if len(device_id) > 4:
                return f"{device_id[:2]}****{device_id[-2:]}"
        return obj.device_id


class LoginSessionSerializer(serializers.ModelSerializer):
    """
    Login session serializer
    """

    user = UserSerializer(read_only=True)
    is_expired = serializers.BooleanField(read_only=True)

    class Meta:
        model = LoginSession
        fields = (
            "id",
            "user",
            "session_token",
            "device_info",
            "ip_address",
            "location",
            "user_agent",
            "is_active",
            "created_at",
            "expires_at",
            "last_activity",
            "is_expired",
        )
        read_only_fields = (
            "session_token",
            "refresh_token",
            "is_expired",
        )


class SecurityEventSerializer(serializers.ModelSerializer):
    """
    Security event serializer
    """

    user = UserSerializer(read_only=True)
    event_type_display = serializers.CharField(
        source="get_event_type_display", read_only=True
    )
    severity_display = serializers.CharField(
        source="get_severity_display", read_only=True
    )

    resolved_by_name = serializers.CharField(
        source="resolved_by.get_full_name", read_only=True
    )

    class Meta:
        model = SecurityEvent
        fields = (
            "id",
            "user",
            "event_type",
            "event_type_display",
            "severity",
            "severity_display",
            "ip_address",
            "user_agent",
            "details",
            "is_resolved",
            "resolved_at",
            "resolved_by",
            "resolved_by_name",
            "timestamp",
        )
        read_only_fields = ("timestamp",)


class AuthenticationAuditSerializer(serializers.ModelSerializer):
    """
    Authentication audit serializer
    """

    user = UserSerializer(read_only=True)
    action_display = serializers.CharField(source="get_action_display", read_only=True)

    class Meta:
        model = AuthenticationAudit
        fields = (
            "id",
            "user",
            "action",
            "action_display",
            "ip_address",
            "user_agent",
            "success",
            "details",
            "resource_accessed",
            "method",
            "endpoint",
            "response_code",
            "timestamp",
        )
        read_only_fields = ("timestamp",)


class DataAccessLogSerializer(serializers.ModelSerializer):
    """
    Data access log serializer
    """

    user = UserSerializer(read_only=True)
    data_type_display = serializers.CharField(
        source="get_data_type_display", read_only=True
    )
    access_type_display = serializers.CharField(
        source="get_access_type_display", read_only=True
    )

    class Meta:
        model = DataAccessLog
        fields = (
            "id",
            "user",
            "data_type",
            "data_type_display",
            "access_type",
            "access_type_display",
            "resource_id",
            "resource_name",
            "ip_address",
            "user_agent",
            "access_reason",
            "details",
            "timestamp",
        )
        read_only_fields = ("timestamp",)


class CustomLoginSerializer(LoginSerializer):
    """
    Enhanced Custom Login serializer with platform support and security features
    """

    platform = serializers.CharField(
        required=False, help_text="Platform identifier for login context"
    )

    def custom_validate(self, username):
        try:
            _username = CustomUser.objects.get(username=username)
            if not _username.is_active:
                # automatically generate and send otp to the user account.
                otp_generated = generate_otp(6)
                _username.otp = otp_generated
                _username.otp_expiry = datetime.now() + timedelta(minutes=5)
                _username.save()

                raise exceptions.InactiveAccountException()
        except ObjectDoesNotExist:
            return username

    def validate(self, attrs):
        request: HttpRequest = self.context.get("request")
        username = attrs.get("username")
        email = attrs.get("email")
        password = attrs.get("password")
        platform = attrs.get("platform")

        # Get client IP for security tracking
        client_ip = self.get_client_ip(request)

        # Rate limiting
        attempt = cache.get(f"login-attempt/{email}")
        if attempt:
            attempt += 1
        else:
            attempt = 1
        cache.set(f"login-attempt/{email}", attempt, 60 * 5)
        if attempt > 5:
            raise exceptions.TooManyLoginAttemptsException()

        if not (username or email):
            raise exceptions.ProvideUsernameOrPasswordException()

        if username:
            user_qs = CustomUser.objects.filter(
                Q(username=username) | Q(email=username)
            )
            if user_qs.exists():
                user = user_qs.first()
                if not user.is_active:
                    raise exceptions.AccountDeactivatedException()
                email = user.email
                attrs["email"] = user.email

            else:
                raise exceptions.UsernameDoesNotExistsException()
        elif email:
            user_qs = CustomUser.objects.filter(email=email)
            if user_qs.exists():
                user = user_qs.first()
                if not user.is_active:
                    raise exceptions.AccountDeactivatedException()
                username = user.username
                attrs["username"] = user.username
            else:
                raise exceptions.EmailDoesNotExistsException()

        _ = self.custom_validate(username)
        user: CustomUser = self.get_auth_user(username, email, password)

        if not user:
            raise exceptions.LoginException()

        # Update last login information
        try:
            user.last_login_ip = client_ip
            user.reset_login_attempts()
            user.save()
        except Exception as e:
            logger.error(f"Error saving last login IP: {str(e)}")

        cache.delete(f"login-attempt/{username}")
        attrs = super().validate(attrs)
        return attrs

    def get_client_ip(self, request):
        """Get client IP address from request"""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0]
        else:
            ip = request.META.get("REMOTE_ADDR")
        return ip


class PlatformProfileSerializer(serializers.Serializer):
    """
    Dynamic serializer for platform-specific profiles
    """

    def to_representation(self, instance):
        """
        Return the appropriate profile serializer based on user platform
        """
        user = instance.user if hasattr(instance, "user") else instance

        # Import serializers dynamically to avoid circular imports
        if hasattr(user, "community_profile"):
            from communities.serializers import OrganizationSerializer

            return OrganizationSerializer(user.community_profile).data
        elif hasattr(user, "professional_profile"):
            from professionals.serializers import ProfessionalProfileSerializer

            return ProfessionalProfileSerializer(user.professional_profile).data
        elif hasattr(user, "facility_profile"):
            from facilities.serializers import FacilityProfileSerializer

            return FacilityProfileSerializer(user.facility_profile).data
        elif hasattr(user, "partner_profile"):
            from partners.serializers import PartnerProfileSerializer

            return PartnerProfileSerializer(user.partner_profile).data
        elif hasattr(user, "pharmacy_profile"):
            from pharmacies.serializers import PharmacyProfileSerializer

            return PharmacyProfileSerializer(user.pharmacy_profile).data
        elif hasattr(user, "patient_profile"):
            from patients.serializers import PatientProfileSerializer

            return PatientProfileSerializer(user.patient_profile).data
        else:
            return UserProfileSerializer(instance).data
