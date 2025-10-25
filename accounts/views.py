from django.db import transaction
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

from communities.models import Organization
from communities.serializers import OrganizationSerializer

from . import serializers
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
from helpers import exceptions
from helpers.functions import generate_otp
from django.core.cache import cache
from .tasks import generic_send_sms, generic_send_mail


# SIGN UP FLOW
class ValidateEmailView(APIView):
    """
    Validate email
    """

    serializer_class = serializers.ValidateEmailSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data.get("email")

        # generate otp

        if CustomUser.objects.filter(email=email).exists():
            return Response(
                data={"status": "error", "message": "Email already exists"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        otp = generate_otp(6)
        print("===  otp: ", otp, "email: ", email)
        cache.set(f"validate_email_otp_{email}", otp, timeout=60 * 5)
        # send otp to email
        generic_send_mail(
            recipient=email,
            title="OTP for email verification",
            payload={
                "otp_code": otp,
                "otp": otp,  # Keep backward compatibility
            },
            email_type="otp",
        )
        return Response(
            data={"status": "success", "message": "OTP sent to email"},
            status=status.HTTP_200_OK,
        )


class ValidatePhoneNumberView(APIView):
    """
    Validate phone number
    """

    serializer_class = serializers.ValidatePhoneNumberSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone_number = serializer.validated_data.get("phone_number")

        print("===  phone number: ", phone_number)

        if CustomUser.objects.filter(phone_number=str(phone_number)).exists():
            return Response(
                data={"status": "error", "message": "Phone number already exists"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        otp = generate_otp(6)
        cache.set(f"validate_phone_number_otp_{str(phone_number)}", otp, timeout=60 * 5)
        # send otp to phone number
        body = """
We received a request to verify your phone number. Your OTP verification code is:
{otp}

This OTP will expire in 5 minutes.
If you did not request this verification, please ignore this message.

Thank you for using BridgeCare.
BridgeCare Team
""".format(
            otp=otp
        )
        generic_send_sms(to=str(phone_number), body=body)
        return Response(
            data={"status": "success", "message": "OTP sent to phone number"},
            status=status.HTTP_200_OK,
        )


class ValidateEmailAndPhoneNumberView(APIView):
    """
    Validate email and phone number
    """

    serializer_class = serializers.ValidateEmailAndPhoneNumberSerializer
    # permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        response_data = {}

        email = serializer.validated_data.get("email")
        phone_number = serializer.validated_data.get("phone_number")

        if CustomUser.objects.filter(phone_number=str(phone_number)).exists():
            response_data["phone_number"] = {
                "status": "error",
                "message": "Phone number already exists",
            }
        else:
            response_data["phone_number"] = {
                "status": "success",
                "message": "Phone number is available",
            }

        if CustomUser.objects.filter(email=email).exists():
            response_data["email"] = {
                "status": "error",
                "message": "Email already exists",
            }
        else:
            response_data["email"] = {
                "status": "success",
                "message": "Email is available",
            }

        return Response(
            data=response_data,
            status=status.HTTP_200_OK,
        )


class VerifyEmailOTPView(APIView):
    """
    Verify email OTP
    """

    serializer_class = serializers.VerifyEmailOTPSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data.get("email")
        otp = serializer.validated_data.get("otp")

        if not cache.get(f"validate_email_otp_{email}"):
            return Response(
                data={"status": "error", "message": "OTP expired"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if cache.get(f"validate_email_otp_{email}") != otp:
            return Response(
                data={"status": "error", "message": "Invalid OTP"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            data={"status": "success", "message": "Email verified"},
            status=status.HTTP_200_OK,
        )


class VerifyPhoneNumberOTPView(APIView):
    """
    Verify phone number OTP
    """

    serializer_class = serializers.VerifyPhoneNumberOTPSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone_number = serializer.validated_data.get("phone_number")
        otp = serializer.validated_data.get("otp")

        if not cache.get(f"validate_phone_number_otp_{str(phone_number)}"):
            return Response(
                data={"status": "error", "message": "OTP expired"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if cache.get(f"validate_phone_number_otp_{str(phone_number)}") != otp:
            return Response(
                data={"status": "error", "message": "Invalid OTP"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            data={"status": "success", "message": "Phone number verified"},
            status=status.HTTP_200_OK,
        )


class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing users with platform-specific features
    """

    queryset = CustomUser.objects.all()
    serializer_class = serializers.UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["is_verified", "is_active"]
    search_fields = ["email", "username", "first_name", "last_name", "phone_number"]
    ordering_fields = ["created_at", "last_login", "last_activity"]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        if self.action == "create":
            return serializers.UserCreateSerializer
        return serializers.UserSerializer

    def get_permissions(self):
        """
        Instantiates and returns the list of permissions that this view requires.
        """
        if self.action in ["create"]:
            permission_classes = [permissions.AllowAny]
        elif self.action in ["list"]:
            permission_classes = [permissions.IsAdminUser]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]

    @action(
        detail=False, methods=["get"], permission_classes=[permissions.IsAuthenticated]
    )
    def me(self, request):
        """Get current user profile"""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(
        detail=False,
        methods=["patch"],
        permission_classes=[permissions.IsAuthenticated],
    )
    def update_profile(self, request):
        """Update current user profile"""
        serializer = self.get_serializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CreateOrganizationUserView(APIView):
    """
    Create an organization user
    """

    serializer_class = serializers.CreateOrganizationUserSerializer
    permission_classes = [permissions.AllowAny]

    @transaction.atomic
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        # create user
        user = CustomUser.objects.create_user(
            username=data["organization_email"],
            email=data["organization_email"],
            password=data["password"],
            phone_number=data["organization_phone"],
        )
        # create organization
        organization = Organization.objects.create(
            user=user,
            organization_name=data["organization_name"],
            organization_type=data["organization_type"],
            organization_phone=data["organization_phone"],
            organization_email=data["organization_email"],
            registration_number=data["registration_number"],
        )

        return Response(
            data=OrganizationSerializer(
                instance=organization, context={"request": request}
            ).data,
            status=status.HTTP_201_CREATED,
        )


class UserProfileViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing user profiles
    """

    queryset = UserProfile.objects.all()
    serializer_class = serializers.UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    search_fields = ["user__email", "user__username", "location"]

    def get_permissions(self):
        if self.action in ["list"]:
            permission_classes = [permissions.IsAdminUser]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]


class RoleViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing roles
    """

    queryset = Role.objects.all()
    serializer_class = serializers.RoleSerializer
    permission_classes = [permissions.IsAdminUser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["is_active"]
    search_fields = ["name", "description"]
    ordering = ["name"]


class UserRoleViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing user role assignments
    """

    queryset = UserRole.objects.all()
    serializer_class = serializers.UserRoleSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["user", "role", "facility", "is_active"]
    search_fields = ["user__email", "role__name", "facility__name"]
    ordering_fields = ["assigned_at", "expires_at"]
    ordering = ["-assigned_at"]

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [permissions.IsAdminUser]
        return [permission() for permission in permission_classes]

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAdminUser])
    def deactivate_role(self, request, pk=None):
        """Deactivate user role"""
        user_role = self.get_object()
        user_role.is_active = False
        user_role.save()
        return Response({"message": "Role deactivated"})


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

    @action(
        detail=False, methods=["post"], permission_classes=[permissions.IsAuthenticated]
    )
    def setup_device(self, request):
        """Setup MFA device for current user"""
        device_type = request.data.get("device_type")
        device_id = request.data.get("device_id")
        device_name = request.data.get("device_name", "")

        if not device_type or not device_id:
            return Response(
                {"error": "device_type and device_id are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        device, created = MFADevice.objects.get_or_create(
            user=request.user,
            device_type=device_type,
            device_id=device_id,
            defaults={"device_name": device_name},
        )

        if not created:
            return Response(
                {"error": "Device already exists"}, status=status.HTTP_400_BAD_REQUEST
            )

        serializer = self.get_serializer(device)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(
        detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated]
    )
    def verify_device(self, request, pk=None):
        """Verify MFA device with OTP"""
        device = self.get_object()

        if device.user != request.user and not request.user.is_staff:
            return Response(
                {"error": "Permission denied"}, status=status.HTTP_403_FORBIDDEN
            )

        otp_code = request.data.get("otp_code")
        if not otp_code:
            return Response(
                {"error": "OTP code is required"}, status=status.HTTP_400_BAD_REQUEST
            )

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
    filterset_fields = ["is_active"]
    ordering_fields = ["created_at", "last_activity"]
    ordering = ["-created_at"]

    def get_queryset(self):
        if self.request.user.is_staff:
            return LoginSession.objects.all()
        return LoginSession.objects.filter(user=self.request.user)

    @action(
        detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated]
    )
    def terminate_session(self, request, pk=None):
        """Terminate a specific login session"""
        session = self.get_object()

        if session.user != request.user and not request.user.is_staff:
            return Response(
                {"error": "Permission denied"}, status=status.HTTP_403_FORBIDDEN
            )

        session.is_active = False
        session.save()
        return Response({"message": "Session terminated"})


class SecurityEventViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing security events (read-only for audit trail integrity)
    """

    queryset = SecurityEvent.objects.all()
    serializer_class = serializers.SecurityEventSerializer
    permission_classes = [permissions.IsAdminUser]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["event_type", "severity", "is_resolved"]
    ordering_fields = ["timestamp"]
    ordering = ["-timestamp"]

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAdminUser])
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
    filterset_fields = ["action", "success", "response_code"]
    ordering_fields = ["timestamp"]
    ordering = ["-timestamp"]


class DataAccessLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing data access logs (read-only for audit trail integrity)
    """

    queryset = DataAccessLog.objects.all()
    serializer_class = serializers.DataAccessLogSerializer
    permission_classes = [permissions.IsAdminUser]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["data_type", "access_type", "platform"]
    ordering_fields = ["timestamp"]
    ordering = ["-timestamp"]


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
            return Response(
                {"error": "Profile not found"}, status=status.HTTP_404_NOT_FOUND
            )

    def patch(self, request):
        """Update platform-specific profile using lazy imports"""
        user = request.user
        try:
            profile = user.profile

            # Get the appropriate serializer based on platform with lazy imports
            if user.platform == "communities" and hasattr(user, "community_profile"):
                from communities.serializers import OrganizationSerializer

                serializer = OrganizationSerializer(
                    user.community_profile, data=request.data, partial=True
                )
            elif user.platform == "professionals" and hasattr(
                user, "professional_profile"
            ):
                from professionals.serializers import ProfessionalProfileSerializer

                serializer = ProfessionalProfileSerializer(
                    user.professional_profile, data=request.data, partial=True
                )
            elif user.platform == "facilities" and hasattr(user, "facility_profile"):
                from facilities.serializers import FacilityProfileSerializer

                serializer = FacilityProfileSerializer(
                    user.facility_profile, data=request.data, partial=True
                )
            elif user.platform == "partners" and hasattr(user, "partner_profile"):
                from partners.serializers import PartnerProfileSerializer

                serializer = PartnerProfileSerializer(
                    user.partner_profile, data=request.data, partial=True
                )
            elif user.platform == "pharmacies" and hasattr(user, "pharmacy_profile"):
                from pharmacies.serializers import PharmacyProfileSerializer

                serializer = PharmacyProfileSerializer(
                    user.pharmacy_profile, data=request.data, partial=True
                )
            elif user.platform == "patients" and hasattr(user, "patient_profile"):
                from patients.serializers import PatientProfileSerializer

                serializer = PatientProfileSerializer(
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
            return Response(
                {"error": "Profile not found"}, status=status.HTTP_404_NOT_FOUND
            )
