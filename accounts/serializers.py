from rest_framework import serializers
from .models import (
    CustomUser, Facility, UserProfile, CommunityProfile, ProfessionalProfile,
    FacilityProfile, PartnerProfile, PharmacyProfile, PatientProfile,
    Role, UserRole, MFADevice, LoginSession, SecurityEvent,
    AuthenticationAudit, DataAccessLog, GuestUser, LocumRequest,
    PrescriptionRequest, AppointmentRequest, EventRegistration
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


class UserCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for user creation with password handling
    """
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)
    
    class Meta:
        model = CustomUser
        fields = [
            'username', 'email', 'password', 'password_confirm', 'first_name', 
            'last_name', 'phone_number', 'date_of_birth', 'platform', 'primary_role'
        ]
        extra_kwargs = {
            'password': {'write_only': True},
        }

    def validate(self, attrs):
        """Validate password confirmation"""
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("Passwords don't match.")
        return attrs

    def create(self, validated_data):
        """Create user with hashed password"""
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        user = CustomUser.objects.create(**validated_data)
        user.set_password(password)
        user.save()
        return user


class UserSerializer(serializers.ModelSerializer):
    """
    Enhanced User serializer with platform support
    """
    platform_display = serializers.CharField(source='get_platform_display', read_only=True)
    primary_role_display = serializers.CharField(source='get_primary_role_display', read_only=True)
    verification_level_display = serializers.CharField(source='get_verification_level_display', read_only=True)
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
            "date_of_birth",
            "profile_picture",
            "platform",
            "platform_display",
            "primary_role",
            "primary_role_display",
            "is_verified",
            "verification_level",
            "verification_level_display",
            "license_number",
            "license_expiry",
            "specializations",
            "mfa_enabled",
            "mfa_method",
            "is_active",
            "is_staff",
            "is_account_locked",
            "created_at",
            "updated_at",
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
            "platform",
            "primary_role",
            "password",
            "password_confirm",
        )

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("Passwords don't match")
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        user = CustomUser.objects.create_user(**validated_data)
        user.set_password(password)
        user.save()
        return user


class FacilitySerializer(serializers.ModelSerializer):
    """
    Facility serializer
    """
    staff_count = serializers.SerializerMethodField()

    class Meta:
        model = Facility
        fields = (
            "id",
            "name",
            "facility_code",
            "facility_type",
            "address",
            "district",
            "region",
            "phone_number",
            "email",
            "latitude",
            "longitude",
            "is_active",
            "staff_count",
            "created_at",
            "updated_at",
        )

    def get_staff_count(self, obj):
        return obj.staff.count()


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Base user profile serializer
    """
    user = UserSerializer(read_only=True)
    platform_display = serializers.CharField(source='get_platform_display', read_only=True)

    class Meta:
        model = UserProfile
        fields = (
            "id",
            "user",
            "platform",
            "platform_display",
            "bio",
            "location",
            "preferred_language",
            "profile_data",
            "created_at",
            "updated_at",
        )


class CommunityProfileSerializer(serializers.ModelSerializer):
    """
    Community profile serializer
    """
    user = UserSerializer(read_only=True)

    class Meta:
        model = CommunityProfile
        fields = (
            "id",
            "user",
            "organization_name",
            "organization_type",
            "volunteer_status",
            "coordinator_level",
            "areas_of_focus",
            "organization_phone",
            "organization_email",
            "organization_address",
            "active_programs",
            "certifications",
            "created_at",
            "updated_at",
        )


class ProfessionalProfileSerializer(serializers.ModelSerializer):
    """
    Professional profile serializer
    """
    user = UserSerializer(read_only=True)
    is_license_valid = serializers.BooleanField(read_only=True)

    class Meta:
        model = ProfessionalProfile
        fields = (
            "id",
            "user",
            "practice_type",
            "years_of_experience",
            "education_background",
            "license_number",
            "license_issuing_body",
            "license_expiry_date",
            "is_license_valid",
            "certifications",
            "availability_schedule",
            "preferred_working_hours",
            "travel_radius",
            "hourly_rate",
            "currency",
            "specializations",
            "languages_spoken",
            "emergency_contact",
            "emergency_phone",
            "created_at",
            "updated_at",
        )


class FacilityProfileSerializer(serializers.ModelSerializer):
    """
    Facility profile serializer
    """
    user = UserSerializer(read_only=True)
    facility = FacilitySerializer(read_only=True)
    supervisor_name = serializers.CharField(source='supervisor.get_full_name', read_only=True)

    class Meta:
        model = FacilityProfile
        fields = (
            "id",
            "user",
            "facility",
            "employee_id",
            "department",
            "position",
            "employment_type",
            "hire_date",
            "shift_schedule",
            "working_hours",
            "can_prescribe",
            "can_access_patient_data",
            "can_manage_inventory",
            "can_schedule_appointments",
            "supervisor",
            "supervisor_name",
            "created_at",
            "updated_at",
        )


class PartnerProfileSerializer(serializers.ModelSerializer):
    """
    Partner profile serializer
    """
    user = UserSerializer(read_only=True)

    class Meta:
        model = PartnerProfile
        fields = (
            "id",
            "user",
            "organization_name",
            "organization_type",
            "organization_size",
            "organization_phone",
            "organization_email",
            "organization_address",
            "website",
            "partnership_type",
            "partnership_status",
            "partnership_start_date",
            "partnership_end_date",
            "api_access_level",
            "can_access_analytics",
            "can_manage_subsidies",
            "can_view_patient_data",
            "contact_person_name",
            "contact_person_title",
            "contact_person_phone",
            "created_at",
            "updated_at",
        )


class PharmacyProfileSerializer(serializers.ModelSerializer):
    """
    Pharmacy profile serializer
    """
    user = UserSerializer(read_only=True)

    class Meta:
        model = PharmacyProfile
        fields = (
            "id",
            "user",
            "pharmacy_name",
            "pharmacy_license",
            "pharmacy_type",
            "address",
            "district",
            "region",
            "latitude",
            "longitude",
            "phone_number",
            "email",
            "website",
            "services_offered",
            "delivery_available",
            "delivery_radius",
            "operating_hours",
            "pharmacist_license",
            "staff_count",
            "payment_methods",
            "insurance_accepted",
            "created_at",
            "updated_at",
        )


class PatientProfileSerializer(serializers.ModelSerializer):
    """
    Patient profile serializer
    """
    user = UserSerializer(read_only=True)
    bmi = serializers.SerializerMethodField()
    preferred_pharmacy_name = serializers.CharField(source='preferred_pharmacy.pharmacy_name', read_only=True)

    class Meta:
        model = PatientProfile
        fields = (
            "id",
            "user",
            "blood_type",
            "height",
            "weight",
            "bmi",
            "emergency_contact_name",
            "emergency_contact_phone",
            "emergency_contact_relationship",
            "insurance_provider",
            "insurance_number",
            "preferred_payment_method",
            "preferred_language",
            "preferred_consultation_type",
            "notification_preferences",
            "medical_history",
            "allergies",
            "current_medications",
            "home_address",
            "work_address",
            "preferred_pharmacy",
            "preferred_pharmacy_name",
            "created_at",
            "updated_at",
        )

    def get_bmi(self, obj):
        return obj.calculate_bmi()


class RoleSerializer(serializers.ModelSerializer):
    """
    Role serializer
    """
    platform_display = serializers.CharField(source='get_platform_display', read_only=True)
    user_count = serializers.SerializerMethodField()

    class Meta:
        model = Role
        fields = (
            "id",
            "name",
            "platform",
            "platform_display",
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
    facility = FacilitySerializer(read_only=True)
    assigned_by_name = serializers.CharField(source='assigned_by.get_full_name', read_only=True)
    is_expired = serializers.BooleanField(read_only=True)

    class Meta:
        model = UserRole
        fields = (
            "id",
            "user",
            "role",
            "facility",
            "assigned_by",
            "assigned_by_name",
            "assigned_at",
            "expires_at",
            "is_active",
            "is_expired",
            "notes",
        )


class MFADeviceSerializer(serializers.ModelSerializer):
    """
    MFA device serializer
    """
    device_type_display = serializers.CharField(source='get_device_type_display', read_only=True)
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
        if obj.device_type in ['sms', 'email']:
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
    event_type_display = serializers.CharField(source='get_event_type_display', read_only=True)
    severity_display = serializers.CharField(source='get_severity_display', read_only=True)
    platform_display = serializers.CharField(source='get_platform_display', read_only=True)
    resolved_by_name = serializers.CharField(source='resolved_by.get_full_name', read_only=True)

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
            "platform",
            "platform_display",
            "details",
            "is_resolved",
            "resolved_at",
            "resolved_by",
            "resolved_by_name",
            "timestamp",
        )
        read_only_fields = (
            "timestamp",
        )


class AuthenticationAuditSerializer(serializers.ModelSerializer):
    """
    Authentication audit serializer
    """
    user = UserSerializer(read_only=True)
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    platform_display = serializers.CharField(source='get_platform_display', read_only=True)

    class Meta:
        model = AuthenticationAudit
        fields = (
            "id",
            "user",
            "action",
            "action_display",
            "platform",
            "platform_display",
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
        read_only_fields = (
            "timestamp",
        )


class DataAccessLogSerializer(serializers.ModelSerializer):
    """
    Data access log serializer
    """
    user = UserSerializer(read_only=True)
    data_type_display = serializers.CharField(source='get_data_type_display', read_only=True)
    access_type_display = serializers.CharField(source='get_access_type_display', read_only=True)
    platform_display = serializers.CharField(source='get_platform_display', read_only=True)

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
            "platform",
            "platform_display",
            "ip_address",
            "user_agent",
            "access_reason",
            "details",
            "timestamp",
        )
        read_only_fields = (
            "timestamp",
        )


class CustomLoginSerializer(LoginSerializer):
    """
    Enhanced Custom Login serializer with platform support and security features
    """
    platform = serializers.CharField(required=False, help_text="Platform identifier for login context")

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
        attempt = cache.get(f"login-attempt/{username}")
        if attempt:
            attempt += 1
        else:
            attempt = 1
        cache.set(f"login-attempt/{username}", attempt, 60 * 5)
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
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class PlatformProfileSerializer(serializers.Serializer):
    """
    Dynamic serializer for platform-specific profiles
    """
    def to_representation(self, instance):
        """
        Return the appropriate profile serializer based on user platform
        """
        user = instance.user if hasattr(instance, 'user') else instance
        
        if hasattr(user, 'community_profile'):
            return CommunityProfileSerializer(user.community_profile).data
        elif hasattr(user, 'professional_profile'):
            return ProfessionalProfileSerializer(user.professional_profile).data
        elif hasattr(user, 'facility_profile'):
            return FacilityProfileSerializer(user.facility_profile).data
        elif hasattr(user, 'partner_profile'):
            return PartnerProfileSerializer(user.partner_profile).data
        elif hasattr(user, 'pharmacy_profile'):
            return PharmacyProfileSerializer(user.pharmacy_profile).data
        elif hasattr(user, 'patient_profile'):
            return PatientProfileSerializer(user.patient_profile).data
        else:
            return UserProfileSerializer(instance).data


# ====================
# General User & Service Request Serializers
# ====================

class GuestUserSerializer(serializers.ModelSerializer):
    """
    Serializer for guest users who haven't registered yet
    """
    class Meta:
        model = GuestUser
        fields = [
            'id', 'email', 'phone_number', 'first_name', 'last_name',
            'location', 'district', 'region', 'preferred_language',
            'newsletter_subscription', 'is_converted', 'created_at'
        ]
        read_only_fields = ['id', 'is_converted', 'created_at']


class LocumRequestSerializer(serializers.ModelSerializer):
    """
    Serializer for locum requests
    """
    facility_name_display = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    urgency_display = serializers.CharField(source='get_urgency_display', read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    requester_info = serializers.SerializerMethodField()
    
    class Meta:
        model = LocumRequest
        fields = [
            'id', 'requester_user', 'requester_guest', 'requester_info',
            'facility', 'facility_name', 'facility_name_display', 'facility_address',
            'position_title', 'specialty_required', 'department',
            'start_date', 'end_date', 'duration_days', 'shift_type', 'hours_per_week',
            'minimum_experience_years', 'license_requirements',
            'certifications_required', 'skills_required',
            'offered_rate', 'rate_type', 'accommodation_provided', 'transportation_provided',
            'urgency', 'urgency_display', 'description', 'special_requirements',
            'status', 'status_display', 'matched_professional', 'is_expired',
            'contact_person', 'contact_email', 'contact_phone',
            'created_at', 'updated_at', 'expires_at'
        ]
        read_only_fields = ['id', 'duration_days', 'created_at', 'updated_at']
    
    def get_facility_name_display(self, obj):
        if obj.facility:
            return obj.facility.name
        return obj.facility_name
    
    def get_requester_info(self, obj):
        if obj.requester_user:
            return {
                'type': 'user',
                'email': obj.requester_user.email,
                'name': f"{obj.requester_user.first_name} {obj.requester_user.last_name}"
            }
        elif obj.requester_guest:
            return {
                'type': 'guest',
                'email': obj.requester_guest.email,
                'name': f"{obj.requester_guest.first_name} {obj.requester_guest.last_name}"
            }
        return None


class PrescriptionRequestSerializer(serializers.ModelSerializer):
    """
    Serializer for prescription requests
    """
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    pharmacy_name = serializers.SerializerMethodField()
    requester_info = serializers.SerializerMethodField()
    
    class Meta:
        model = PrescriptionRequest
        fields = [
            'id', 'requester_user', 'requester_guest', 'requester_info',
            'prescription_image', 'prescription_number',
            'medication_name', 'dosage', 'quantity', 'refills',
            'prescribing_doctor', 'diagnosis', 'notes',
            'preferred_pharmacy', 'pharmacy_name', 'delivery_required', 'delivery_address',
            'status', 'status_display', 'approved_by',
            'created_at', 'updated_at', 'expires_at'
        ]
        read_only_fields = ['id', 'prescription_number', 'approved_by', 'created_at', 'updated_at']
    
    def get_pharmacy_name(self, obj):
        if obj.preferred_pharmacy:
            if hasattr(obj.preferred_pharmacy, 'pharmacy_profile'):
                return obj.preferred_pharmacy.pharmacy_profile.pharmacy_name
            return obj.preferred_pharmacy.email
        return None
    
    def get_requester_info(self, obj):
        if obj.requester_user:
            return {
                'type': 'user',
                'email': obj.requester_user.email,
                'name': f"{obj.requester_user.first_name} {obj.requester_user.last_name}"
            }
        elif obj.requester_guest:
            return {
                'type': 'guest',
                'email': obj.requester_guest.email,
                'name': f"{obj.requester_guest.first_name} {obj.requester_guest.last_name}"
            }
        return None


class AppointmentRequestSerializer(serializers.ModelSerializer):
    """
    Serializer for appointment requests
    """
    appointment_type_display = serializers.CharField(source='get_appointment_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    facility_name = serializers.SerializerMethodField()
    professional_name = serializers.SerializerMethodField()
    requester_info = serializers.SerializerMethodField()
    
    class Meta:
        model = AppointmentRequest
        fields = [
            'id', 'requester_user', 'requester_guest', 'requester_info',
            'appointment_type', 'appointment_type_display',
            'preferred_date', 'preferred_time', 'alternative_dates',
            'facility', 'facility_name', 'preferred_professional', 'professional_name',
            'patient_name', 'patient_age', 'patient_gender', 'patient_phone', 'patient_email',
            'reason_for_visit', 'symptoms', 'medical_history', 'current_medications', 'allergies',
            'has_insurance', 'insurance_provider', 'insurance_number',
            'status', 'status_display', 'confirmed_date', 'confirmed_time', 'confirmation_code',
            'notes', 'admin_notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'confirmation_code', 'created_at', 'updated_at']
    
    def get_facility_name(self, obj):
        if obj.facility:
            return obj.facility.name
        return None
    
    def get_professional_name(self, obj):
        if obj.preferred_professional:
            return f"{obj.preferred_professional.first_name} {obj.preferred_professional.last_name}"
        return None
    
    def get_requester_info(self, obj):
        if obj.requester_user:
            return {
                'type': 'user',
                'email': obj.requester_user.email,
                'name': f"{obj.requester_user.first_name} {obj.requester_user.last_name}"
            }
        elif obj.requester_guest:
            return {
                'type': 'guest',
                'email': obj.requester_guest.email,
                'name': f"{obj.requester_guest.first_name} {obj.requester_guest.last_name}"
            }
        return None


class EventRegistrationSerializer(serializers.ModelSerializer):
    """
    Serializer for event registrations
    """
    event_type_display = serializers.CharField(source='get_event_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    organizer_name = serializers.SerializerMethodField()
    registrant_info = serializers.SerializerMethodField()
    
    class Meta:
        model = EventRegistration
        fields = [
            'id', 'registrant_user', 'registrant_guest', 'registrant_info',
            'event_name', 'event_date', 'event_time', 'event_location',
            'event_type', 'event_type_display', 'organized_by', 'organizer_name',
            'participant_name', 'participant_email', 'participant_phone', 'participant_age',
            'number_of_attendees', 'special_requirements', 'dietary_restrictions',
            'status', 'status_display', 'registration_code',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'registration_code', 'created_at', 'updated_at']
    
    def get_organizer_name(self, obj):
        if obj.organized_by:
            return f"{obj.organized_by.first_name} {obj.organized_by.last_name}"
        return None
    
    def get_registrant_info(self, obj):
        if obj.registrant_user:
            return {
                'type': 'user',
                'email': obj.registrant_user.email,
                'name': f"{obj.registrant_user.first_name} {obj.registrant_user.last_name}"
            }
        elif obj.registrant_guest:
            return {
                'type': 'guest',
                'email': obj.registrant_guest.email,
                'name': f"{obj.registrant_guest.first_name} {obj.registrant_guest.last_name}"
            }
        return None
