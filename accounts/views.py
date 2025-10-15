from rest_framework import viewsets, status, permissions, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from django.contrib.auth import authenticate
from django.utils import timezone
from django.db.models import Q
from django.shortcuts import get_object_or_404
from loguru import logger

from . import serializers
from .models import (
    CustomUser, Facility, UserProfile, CommunityProfile, ProfessionalProfile,
    FacilityProfile, PartnerProfile, PharmacyProfile, PatientProfile,
    Role, UserRole, MFADevice, LoginSession, SecurityEvent,
    AuthenticationAudit, DataAccessLog, GuestUser, LocumRequest,
    PrescriptionRequest, AppointmentRequest, EventRegistration
)
from helpers import exceptions
from helpers.functions import generate_otp


class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing users with platform-specific features
    """
    queryset = CustomUser.objects.all()
    serializer_class = serializers.UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['platform', 'primary_role', 'verification_level', 'is_verified', 'is_active']
    search_fields = ['email', 'username', 'first_name', 'last_name', 'phone_number']
    ordering_fields = ['created_at', 'last_login', 'last_activity']
    ordering = ['-created_at']

    def get_serializer_class(self):
        if self.action == 'create':
            return serializers.UserCreateSerializer
        return serializers.UserSerializer

    def get_permissions(self):
        """
        Instantiates and returns the list of permissions that this view requires.
        """
        if self.action in ['create']:
            permission_classes = [permissions.AllowAny]
        elif self.action in ['list']:
            permission_classes = [permissions.IsAdminUser]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]

    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def me(self, request):
        """Get current user profile"""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(detail=False, methods=['patch'], permission_classes=[permissions.IsAuthenticated])
    def update_profile(self, request):
        """Update current user profile"""
        serializer = self.get_serializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def assign_role(self, request, pk=None):
        """Assign role to user"""
        user = self.get_object()
        role_id = request.data.get('role_id')
        facility_id = request.data.get('facility_id')
        expires_at = request.data.get('expires_at')
        notes = request.data.get('notes', '')

        if not role_id:
            return Response({'error': 'role_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            role = Role.objects.get(id=role_id)
            facility = None
            if facility_id:
                facility = Facility.objects.get(id=facility_id)

            user_role, created = UserRole.objects.get_or_create(
                user=user,
                role=role,
                facility=facility,
                defaults={
                    'assigned_by': request.user,
                    'expires_at': expires_at,
                    'notes': notes
                }
            )

            if not created:
                return Response({'error': 'Role already assigned'}, status=status.HTTP_400_BAD_REQUEST)

            serializer = serializers.UserRoleSerializer(user_role)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except Role.DoesNotExist:
            return Response({'error': 'Role not found'}, status=status.HTTP_404_NOT_FOUND)
        except Facility.DoesNotExist:
            return Response({'error': 'Facility not found'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def lock_account(self, request, pk=None):
        """Lock user account"""
        user = self.get_object()
        duration_minutes = request.data.get('duration_minutes', 30)
        user.lock_account(duration_minutes)
        return Response({'message': f'Account locked for {duration_minutes} minutes'})

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def unlock_account(self, request, pk=None):
        """Unlock user account"""
        user = self.get_object()
        user.unlock_account()
        return Response({'message': 'Account unlocked'})


class FacilityViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing health facilities
    """
    queryset = Facility.objects.all()
    serializer_class = serializers.FacilitySerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['facility_type', 'district', 'region', 'is_active']
    search_fields = ['name', 'facility_code', 'district', 'region']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [permissions.IsAdminUser]
        return [permission() for permission in permission_classes]


class UserProfileViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing user profiles
    """
    queryset = UserProfile.objects.all()
    serializer_class = serializers.UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['platform']
    search_fields = ['user__email', 'user__username', 'location']

    def get_permissions(self):
        if self.action in ['list']:
            permission_classes = [permissions.IsAdminUser]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]


class CommunityProfileViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing community profiles
    """
    queryset = CommunityProfile.objects.all()
    serializer_class = serializers.CommunityProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['organization_type', 'volunteer_status', 'coordinator_level']
    search_fields = ['user__email', 'organization_name', 'organization_type']

    def get_permissions(self):
        if self.action in ['list']:
            permission_classes = [permissions.IsAdminUser]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]


class ProfessionalProfileViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing professional profiles
    """
    queryset = ProfessionalProfile.objects.all()
    serializer_class = serializers.ProfessionalProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['practice_type', 'years_of_experience', 'license_issuing_body']
    search_fields = ['user__email', 'license_number', 'practice_type']
    ordering_fields = ['years_of_experience', 'hourly_rate']
    ordering = ['-years_of_experience']

    def get_permissions(self):
        if self.action in ['list']:
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]

    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def available_locums(self, request):
        """Get available locum professionals"""
        queryset = self.get_queryset().filter(
            availability_schedule__isnull=False,
            user__is_active=True
        )
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class FacilityProfileViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing facility profiles
    """
    queryset = FacilityProfile.objects.all()
    serializer_class = serializers.FacilityProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['facility', 'department', 'position', 'employment_type']
    search_fields = ['user__email', 'facility__name', 'employee_id', 'position']

    def get_permissions(self):
        if self.action in ['list']:
            permission_classes = [permissions.IsAdminUser]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]


class PartnerProfileViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing partner profiles
    """
    queryset = PartnerProfile.objects.all()
    serializer_class = serializers.PartnerProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['organization_type', 'partnership_type', 'partnership_status', 'api_access_level']
    search_fields = ['user__email', 'organization_name', 'organization_type']

    def get_permissions(self):
        if self.action in ['list']:
            permission_classes = [permissions.IsAdminUser]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]


class PharmacyProfileViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing pharmacy profiles
    """
    queryset = PharmacyProfile.objects.all()
    serializer_class = serializers.PharmacyProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['pharmacy_type', 'district', 'region', 'delivery_available']
    search_fields = ['user__email', 'pharmacy_name', 'pharmacy_license', 'district']
    ordering_fields = ['pharmacy_name']
    ordering = ['pharmacy_name']

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]

    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def nearby_pharmacies(self, request):
        """Get pharmacies near a location"""
        latitude = request.query_params.get('lat')
        longitude = request.query_params.get('lng')
        radius = request.query_params.get('radius', 10)  # km

        if not latitude or not longitude:
            return Response({'error': 'Latitude and longitude are required'}, 
                          status=status.HTTP_400_BAD_REQUEST)

        # Simple distance calculation (in production, use PostGIS or similar)
        queryset = self.get_queryset().filter(
            latitude__isnull=False,
            longitude__isnull=False,
            user__is_active=True
        )
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class PatientProfileViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing patient profiles
    """
    queryset = PatientProfile.objects.all()
    serializer_class = serializers.PatientProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['blood_type', 'preferred_consultation_type', 'preferred_payment_method']
    search_fields = ['user__email', 'emergency_contact_name', 'insurance_provider']

    def get_permissions(self):
        if self.action in ['list']:
            permission_classes = [permissions.IsAdminUser]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def update_health_info(self, request, pk=None):
        """Update patient health information"""
        patient = self.get_object()
        
        # Check if user can access this patient's data
        if not (request.user.is_staff or patient.user == request.user):
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

        serializer = self.get_serializer(patient, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RoleViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing roles
    """
    queryset = Role.objects.all()
    serializer_class = serializers.RoleSerializer
    permission_classes = [permissions.IsAdminUser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['platform', 'is_active']
    search_fields = ['name', 'platform', 'description']
    ordering = ['platform', 'name']


class UserRoleViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing user role assignments
    """
    queryset = UserRole.objects.all()
    serializer_class = serializers.UserRoleSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['user', 'role', 'facility', 'is_active']
    search_fields = ['user__email', 'role__name', 'facility__name']
    ordering_fields = ['assigned_at', 'expires_at']
    ordering = ['-assigned_at']

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [permissions.IsAdminUser]
        return [permission() for permission in permission_classes]

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def deactivate_role(self, request, pk=None):
        """Deactivate user role"""
        user_role = self.get_object()
        user_role.is_active = False
        user_role.save()
        return Response({'message': 'Role deactivated'})


class MFADeviceViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing MFA devices
    """
    queryset = MFADevice.objects.all()
    serializer_class = serializers.MFADeviceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return MFADevice.objects.all()
        return MFADevice.objects.filter(user=self.request.user)

    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def setup_device(self, request):
        """Setup MFA device for current user"""
        device_type = request.data.get('device_type')
        device_id = request.data.get('device_id')
        device_name = request.data.get('device_name', '')

        if not device_type or not device_id:
            return Response({'error': 'device_type and device_id are required'}, 
                          status=status.HTTP_400_BAD_REQUEST)

        device, created = MFADevice.objects.get_or_create(
            user=request.user,
            device_type=device_type,
            device_id=device_id,
            defaults={'device_name': device_name}
        )

        if not created:
            return Response({'error': 'Device already exists'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(device)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def verify_device(self, request, pk=None):
        """Verify MFA device with OTP"""
        device = self.get_object()
        
        if device.user != request.user and not request.user.is_staff:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

        otp_code = request.data.get('otp_code')
        if not otp_code:
            return Response({'error': 'OTP code is required'}, status=status.HTTP_400_BAD_REQUEST)

        # Here you would verify the OTP code
        # For now, we'll just mark it as verified
        device.is_verified = True
        device.save()

        serializer = self.get_serializer(device)
        return Response(serializer.data)


class LoginSessionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing login sessions (read-only for security)
    """
    queryset = LoginSession.objects.all()
    serializer_class = serializers.LoginSessionSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['is_active']
    ordering_fields = ['created_at', 'last_activity']
    ordering = ['-created_at']

    def get_queryset(self):
        if self.request.user.is_staff:
            return LoginSession.objects.all()
        return LoginSession.objects.filter(user=self.request.user)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def terminate_session(self, request, pk=None):
        """Terminate a specific login session"""
        session = self.get_object()
        
        if session.user != request.user and not request.user.is_staff:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

        session.is_active = False
        session.save()
        return Response({'message': 'Session terminated'})


class SecurityEventViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing security events (read-only for audit trail integrity)
    """
    queryset = SecurityEvent.objects.all()
    serializer_class = serializers.SecurityEventSerializer
    permission_classes = [permissions.IsAdminUser]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['event_type', 'severity', 'platform', 'is_resolved']
    ordering_fields = ['timestamp']
    ordering = ['-timestamp']

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def resolve_event(self, request, pk=None):
        """Mark security event as resolved"""
        event = self.get_object()
        event.is_resolved = True
        event.resolved_at = timezone.now()
        event.resolved_by = request.user
        event.save()
        
        serializer = self.get_serializer(event)
        return Response(serializer.data)


class AuthenticationAuditViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing authentication audit logs (read-only for audit trail integrity)
    """
    queryset = AuthenticationAudit.objects.all()
    serializer_class = serializers.AuthenticationAuditSerializer
    permission_classes = [permissions.IsAdminUser]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['action', 'platform', 'success', 'response_code']
    ordering_fields = ['timestamp']
    ordering = ['-timestamp']


class DataAccessLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing data access logs (read-only for audit trail integrity)
    """
    queryset = DataAccessLog.objects.all()
    serializer_class = serializers.DataAccessLogSerializer
    permission_classes = [permissions.IsAdminUser]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['data_type', 'access_type', 'platform']
    ordering_fields = ['timestamp']
    ordering = ['-timestamp']


# Custom API Views for specific functionality
class ProfileView(APIView):
    """
    Legacy profile view for backward compatibility
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        serializer = serializers.UserSerializer(request.user)
        return Response(serializer.data)


class PlatformProfileView(APIView):
    """
    Get platform-specific profile for current user
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        try:
            profile = user.profile
            serializer = serializers.PlatformProfileSerializer(profile)
            return Response(serializer.data)
        except UserProfile.DoesNotExist:
            return Response({'error': 'Profile not found'}, status=status.HTTP_404_NOT_FOUND)

    def patch(self, request):
        """Update platform-specific profile"""
        user = request.user
        try:
            profile = user.profile
            
            # Get the appropriate serializer based on platform
            if user.platform == 'communities' and hasattr(user, 'community_profile'):
                serializer = serializers.CommunityProfileSerializer(
                    user.community_profile, data=request.data, partial=True
                )
            elif user.platform == 'professionals' and hasattr(user, 'professional_profile'):
                serializer = serializers.ProfessionalProfileSerializer(
                    user.professional_profile, data=request.data, partial=True
                )
            elif user.platform == 'facilities' and hasattr(user, 'facility_profile'):
                serializer = serializers.FacilityProfileSerializer(
                    user.facility_profile, data=request.data, partial=True
                )
            elif user.platform == 'partners' and hasattr(user, 'partner_profile'):
                serializer = serializers.PartnerProfileSerializer(
                    user.partner_profile, data=request.data, partial=True
                )
            elif user.platform == 'pharmacies' and hasattr(user, 'pharmacy_profile'):
                serializer = serializers.PharmacyProfileSerializer(
                    user.pharmacy_profile, data=request.data, partial=True
                )
            elif user.platform == 'patients' and hasattr(user, 'patient_profile'):
                serializer = serializers.PatientProfileSerializer(
                    user.patient_profile, data=request.data, partial=True
                )
            else:
                serializer = serializers.UserProfileSerializer(
                    profile, data=request.data, partial=True
                )

            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except UserProfile.DoesNotExist:
            return Response({'error': 'Profile not found'}, status=status.HTTP_404_NOT_FOUND)


# ====================
# General User & Service Request ViewSets
# ====================

class GuestUserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for guest users (non-registered visitors)
    """
    queryset = GuestUser.objects.all()
    serializer_class = serializers.GuestUserSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_converted', 'region', 'district']
    search_fields = ['email', 'first_name', 'last_name', 'phone_number']
    ordering_fields = ['created_at']
    ordering = ['-created_at']

    def get_permissions(self):
        if self.action in ['create']:
            permission_classes = [permissions.AllowAny]
        elif self.action in ['list']:
            permission_classes = [permissions.IsAdminUser]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]


class LocumRequestViewSet(viewsets.ModelViewSet):
    """
    ViewSet for locum tenens requests
    """
    queryset = LocumRequest.objects.all()
    serializer_class = serializers.LocumRequestSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'urgency', 'specialty_required', 'shift_type']
    search_fields = ['position_title', 'facility_name', 'specialty_required']
    ordering_fields = ['created_at', 'start_date', 'offered_rate']
    ordering = ['-created_at']

    def get_permissions(self):
        if self.action in ['create', 'list', 'retrieve']:
            permission_classes = [permissions.AllowAny]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]

    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def my_requests(self, request):
        """Get locum requests created by current user"""
        queryset = self.get_queryset().filter(requester_user=request.user)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], permission_classes=[permissions.AllowAny])
    def available(self, request):
        """Get available locum requests (pending, not expired)"""
        queryset = self.get_queryset().filter(
            status='pending',
            start_date__gte=timezone.now().date()
        )
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class PrescriptionRequestViewSet(viewsets.ModelViewSet):
    """
    ViewSet for prescription requests
    """
    queryset = PrescriptionRequest.objects.all()
    serializer_class = serializers.PrescriptionRequestSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'delivery_required']
    search_fields = ['medication_name', 'prescription_number']
    ordering_fields = ['created_at']
    ordering = ['-created_at']

    def get_permissions(self):
        if self.action in ['create', 'list', 'retrieve']:
            permission_classes = [permissions.AllowAny]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]


class AppointmentRequestViewSet(viewsets.ModelViewSet):
    """
    ViewSet for appointment requests
    """
    queryset = AppointmentRequest.objects.all()
    serializer_class = serializers.AppointmentRequestSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'appointment_type', 'preferred_date', 'facility']
    search_fields = ['patient_name', 'patient_email', 'confirmation_code']
    ordering_fields = ['created_at', 'preferred_date']
    ordering = ['-created_at']

    def get_permissions(self):
        if self.action in ['create', 'list', 'retrieve']:
            permission_classes = [permissions.AllowAny]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]


class EventRegistrationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for event registrations
    """
    queryset = EventRegistration.objects.all()
    serializer_class = serializers.EventRegistrationSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'event_type', 'event_date']
    search_fields = ['participant_name', 'event_name', 'registration_code']
    ordering_fields = ['created_at', 'event_date']
    ordering = ['-created_at']

    def get_permissions(self):
        if self.action in ['create', 'list', 'retrieve']:
            permission_classes = [permissions.AllowAny]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]

    @action(detail=False, methods=['get'], permission_classes=[permissions.AllowAny])
    def upcoming_events(self, request):
        """Get upcoming events available for registration"""
        queryset = self.get_queryset().filter(
            event_date__gte=timezone.now().date()
        ).order_by('event_date')
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
