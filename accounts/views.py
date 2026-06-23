from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.middleware.csrf import get_token
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.decorators import method_decorator
from rest_framework import viewsets, status, permissions, filters
from rest_framework.decorators import (
    action,
    api_view,
    permission_classes as drf_permission_classes,
)
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from facilities.models import FacilityProfile
from helpers import exceptions
from communities.models import Organization
from communities.serializers import OrganizationSerializer
from . import serializers
from .models import (
    CustomUser,
    Role,
    UserRole,
    MFADevice,
    LoginSession,
    SecurityEvent,
    AuthenticationAudit,
    DataAccessLog,
    Address,
)
from helpers.functions import generate_otp
from django.core.cache import cache
from .tasks import generic_send_sms, generic_send_mail
from professionals.models import Profession, ProfessionalProfile
from professionals.serializers import ProfessionalProfileSerializer
from pharmacies.models import PharmacyProfile
from pharmacies.serializers import PharmacyProfileSerializer
from facilities.serializers import FacilityProfileSerializer


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

        # update user default profile to organization profile
        user.default_profile = organization.id
        user.save()

        generic_send_mail.delay(
            recipient=data["organization_email"],
            title="Welcome to BridgeCare!",
            payload={
                "user_name": data["organization_name"],
                "login_link": settings.FRONTEND_URL,
            },
            email_type="registration",
        )

        return Response(
            data=OrganizationSerializer(
                instance=organization, context={"request": request}
            ).data,
            status=status.HTTP_201_CREATED,
        )


class CreateHealthProfessionalUserView(APIView):
    """
    Create a health professional user
    """

    serializer_class = serializers.CreateHealthProfessionalUserSerializer
    permission_classes = [permissions.AllowAny]

    @transaction.atomic
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        first_name = data.get("first_name", None)
        last_name = data.get("last_name", None)

        # create user
        user = CustomUser.objects.create_user(
            username=data["email"],
            email=data["email"],
            phone_number=data["phone_number"],
            first_name=first_name,
            last_name=last_name,
        )
        user.set_password(data["password"])

        # get profession object
        profession = Profession.objects.get(id=data["profession"])
        # create health professional profile
        health_professional = ProfessionalProfile.objects.create(
            user=user,
            profession=profession,
            is_student=data.get("is_student", False),
        )
        # set user default profile to health professional profile
        user.default_profile = health_professional.id
        user.save()

        full_name = " ".join(filter(None, [first_name, last_name]))
        generic_send_mail.delay(
            recipient=data["email"],
            title="Welcome to BridgeCare — Account Under Verification",
            payload={
                "user_name": full_name or None,
                "login_link": settings.FRONTEND_URL,
            },
            email_type="registration_pending_verification",
        )

        return Response(
            data=ProfessionalProfileSerializer(
                instance=health_professional, context={"request": request}
            ).data,
            status=status.HTTP_201_CREATED,
        )


class CreatePharmacyUserView(APIView):
    """
    Create a health professional user
    """

    serializer_class = serializers.CreatePharmacyUserSerializer
    permission_classes = [permissions.AllowAny]

    @transaction.atomic
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # create user
        user = CustomUser.objects.create_user(
            username=data["email"],
            email=data["email"],
            phone_number=data["phone_number"],
        )
        user.set_password(data["password"])

        # create pharmacy profile
        pharmacy_profile = PharmacyProfile.objects.create(
            user=user,
            pharmacy_name=data["pharmacy_name"],
            pharmacy_license=data["pharmacy_license"],
            license_expiry_date=data["license_expiry_date"],
            address=data["address"],
            phone_number=data["phone_number"],
            email=data["email"],
        )

        # set user default profile to health professional profile
        user.default_profile = pharmacy_profile.id
        user.save()

        generic_send_mail.delay(
            recipient=data["email"],
            title="Welcome to BridgeCare — Account Under Verification",
            payload={
                "user_name": data["pharmacy_name"],
                "login_link": settings.FRONTEND_URL,
            },
            email_type="registration_pending_verification",
        )

        return Response(
            data=PharmacyProfileSerializer(
                instance=pharmacy_profile,
                context={"request": request},
            ).data,
            status=status.HTTP_201_CREATED,
        )


class CreateHealthFacilityProfileView(APIView):
    """
    Create a health facility profile
    """

    serializer_class = serializers.CreateHealthFacilityProfileSerializer
    permission_classes = [permissions.AllowAny]

    @transaction.atomic
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # create user
        user = CustomUser.objects.create_user(
            username=data["email"],
            email=data["email"],
            phone_number=data["phone_number"],
        )
        user.set_password(data["password"])

        # create health facility profile
        facility_profile = FacilityProfile.objects.create(
            user=user,
            phone_number=data["phone_number"],
            email=data["email"],
            name=data["facility_name"],
            facility_type=data["facility_type"],
            latitude=data["latitude"],
            longitude=data["longitude"],
            address=data["address"],
            region=data["region"],
            district=data["district"],
        )

        # set user default profile to health facility profile
        user.default_profile = facility_profile.id
        user.save()

        generic_send_mail.delay(
            recipient=data["email"],
            title="Welcome to BridgeCare — Account Under Verification",
            payload={
                "user_name": data["facility_name"],
                "login_link": settings.FRONTEND_URL,
            },
            email_type="registration_pending_verification",
        )

        return Response(
            data=FacilityProfileSerializer(
                instance=facility_profile,
                context={"request": request},
            ).data,
            status=status.HTTP_201_CREATED,
        )


class CreatePartnerUserView(APIView):
    """Create a partner organisation profile."""

    serializer_class = serializers.CreatePartnerUserSerializer
    permission_classes = [permissions.AllowAny]

    @transaction.atomic
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user = CustomUser.objects.create_user(
            username=data["email"],
            email=data["email"],
            phone_number=data["phone_number"],
        )
        user.set_password(data["password"])
        user.save()

        from partners.models import PartnerProfile

        partner = PartnerProfile.objects.create(
            user=user,
            organization_name=data["organization_name"],
            organization_type=data["organization_type"],
            organization_size=data.get("organization_size", ""),
            registration_number=data.get("registration_number", ""),
            partnership_type=data["partnership_type"],
            organization_phone=data["phone_number"],
            organization_email=data["email"],
            organization_address=data.get("organization_address", ""),
            region=data.get("region", ""),
            district=data.get("district", ""),
            website=data.get("website", "") or None,
            contact_person_name=data.get("contact_person_name", ""),
            contact_person_title=data.get("contact_person_title", ""),
            contact_person_phone=data.get("contact_person_phone") or None,
            is_verified=False,
        )

        user.default_profile = partner.id
        user.save()

        generic_send_mail.delay(
            recipient=data["email"],
            title="Welcome to BridgeCare — Partner Account Under Review",
            payload={
                "user_name": data["organization_name"],
                "login_link": settings.FRONTEND_URL,
            },
            email_type="registration_pending_verification",
        )

        from partners.serializers import PartnerProfileSerializer

        return Response(
            PartnerProfileSerializer(partner, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class CreatePatientUserView(APIView):
    """Create a patient/user account."""

    serializer_class = serializers.CreatePatientUserSerializer
    permission_classes = [permissions.AllowAny]

    @transaction.atomic
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user = CustomUser.objects.create_user(
            username=data["email"],
            email=data["email"],
            phone_number=data["phone_number"],
            first_name=data["first_name"],
            last_name=data["last_name"],
            password=data["password"],
        )

        from patients.models import PatientProfile

        profile, _ = PatientProfile.objects.get_or_create(user=user)
        profile.first_name = data["first_name"]
        profile.last_name = data["last_name"]
        profile.surname = data["last_name"]
        profile.email = data["email"]
        profile.phone_number = data["phone_number"]
        if data.get("date_of_birth"):
            profile.date_of_birth = data["date_of_birth"]
        if data.get("gender"):
            profile.gender = data["gender"]
        if data.get("address"):
            profile.address = data["address"]
        profile.save()

        user.default_profile = profile.id
        user.save()

        try:
            generic_send_mail.delay(
                recipient=data["email"],
                title="Welcome to BridgeCare",
                payload={
                    "user_name": f"{data['first_name']} {data['last_name']}",
                    "login_link": settings.FRONTEND_URL,
                },
                email_type="welcome",
            )
        except Exception:
            pass

        from patients.serializers import PatientProfileSerializer

        return Response(
            PatientProfileSerializer(profile, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


# SIGN UP FLOW
class ValidateEmailView(APIView):
    """
    Validate email
    """

    serializer_class = serializers.ValidateEmailSerializer
    permission_classes = [permissions.AllowAny]
    throttle_scope = "otp"

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
    throttle_scope = "otp"

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone_number = serializer.validated_data.get("phone_number")

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
    Validate email and phone number, then send OTP to email.
    """

    serializer_class = serializers.ValidateEmailAndPhoneNumberSerializer
    permission_classes = [permissions.AllowAny]
    throttle_scope = "otp"

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data.get("email")
        phone_number = serializer.validated_data.get("phone_number")

        if CustomUser.objects.filter(phone_number=str(phone_number)).exists():
            raise exceptions.GeneralException("Phone number already exists")

        if CustomUser.objects.filter(email=email).exists():
            raise exceptions.GeneralException("Email already exists")

        # Generate and cache OTP, then send to email
        otp = generate_otp(6)
        cache.set(f"validate_email_otp_{email}", otp, timeout=60 * 5)
        generic_send_mail(
            recipient=email,
            title="OTP for email verification",
            payload={
                "otp_code": otp,
                "otp": otp,
            },
            email_type="otp",
        )

        return Response(
            data={
                "status": "success",
                "message": "OTP sent to email. Email and phone number are available.",
            },
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


# ACCOUNT SECTION VIEWS
class AccountProfileView(APIView):
    """
    Account profile view
    """

    serializer_class = serializers.AccountProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        serializer = self.serializer_class(request.user)
        return Response(serializer.data)


class AddProfileView(APIView):
    """
    Add a new platform profile to the CURRENT authenticated user.

    This is what lets one human hold multiple profiles (e.g. an org staff member
    who is also a patient). It deliberately bypasses the signup OTP "email/phone
    already in use" checks — those guard brand-new accounts; here the user is
    already a verified identity, so adding a profile to themselves is not a
    collision. Detailed onboarding is completed afterwards via the profile's own
    edit endpoints/wizard.
    """

    permission_classes = [permissions.IsAuthenticated]

    # profile_type -> (module path, model class). The reverse OneToOne accessor
    # name equals the profile_type (e.g. user.patient_profile).
    PROFILE_MODELS = {
        "patient_profile": ("patients.models", "PatientProfile"),
        "professional_profile": ("professionals.models", "ProfessionalProfile"),
        "community_profile": ("communities.models", "Organization"),
        "facility_profile": ("facilities.models", "FacilityProfile"),
        "pharmacy_profile": ("pharmacies.models", "PharmacyProfile"),
        "partner_profile": ("partners.models", "PartnerProfile"),
    }

    def post(self, request):
        import importlib

        profile_type = request.data.get("profile_type")
        if profile_type not in self.PROFILE_MODELS:
            return Response(
                {"status": "error", "message": "Invalid profile type."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user
        existing = getattr(user, profile_type, None)
        if existing is not None:
            return Response(
                {
                    "status": "error",
                    "message": "You already have this profile.",
                    "profile_id": str(existing.id),
                    "profile_type": profile_type,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        module_path, class_name = self.PROFILE_MODELS[profile_type]
        model = getattr(importlib.import_module(module_path), class_name)
        profile, _ = model.objects.get_or_create(user=user)

        # Make the new profile the active context so the user lands in it.
        user.default_profile = profile.id
        user.save()

        return Response(
            {
                "status": "success",
                "message": "Profile added to your account.",
                "profile_type": profile_type,
                "profile_id": str(profile.id),
            },
            status=status.HTTP_201_CREATED,
        )


class AttachPatientProfileView(APIView):
    """
    Add a patient profile to the CURRENT authenticated user (add-mode of the
    patient signup). Reuses the existing identity — no new user, no OTP — so a
    staff member or any existing user can also be a patient.
    """

    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        from patients.models import PatientProfile
        from patients.serializers import PatientProfileSerializer

        user = request.user
        if getattr(user, "patient_profile", None) is not None:
            return Response(
                {
                    "status": "error",
                    "message": "You already have a patient profile.",
                    "profile_id": str(user.patient_profile.id),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = request.data
        first = (data.get("first_name") or user.first_name or "").strip()
        last = (data.get("last_name") or user.last_name or "").strip()

        profile, _ = PatientProfile.objects.get_or_create(user=user)
        profile.first_name = first
        profile.last_name = last
        profile.surname = last
        profile.email = user.email
        profile.phone_number = str(user.phone_number or "")
        if data.get("date_of_birth"):
            profile.date_of_birth = data["date_of_birth"]
        if data.get("gender"):
            profile.gender = data["gender"]
        if data.get("address"):
            profile.address = data["address"]
        profile.save()

        user.default_profile = profile.id
        user.save()

        return Response(
            PatientProfileSerializer(profile, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class AttachProfileView(APIView):
    """
    Add a professional / facility / pharmacy / partner profile to the CURRENT
    authenticated user (add-mode of those signup wizards). Reuses the existing
    identity — no new user, no OTP. Mirrors the field mapping of the matching
    Create<X>UserView. (Patient has its own endpoint.)
    """

    permission_classes = [permissions.IsAuthenticated]

    def _require(self, data, *fields):
        missing = [f for f in fields if not data.get(f)]
        if missing:
            raise exceptions.GeneralException(
                f"Missing required field(s): {', '.join(missing)}"
            )

    @transaction.atomic
    def post(self, request):
        profile_type = request.data.get("profile_type")
        user = request.user
        data = request.data

        if profile_type not in (
            "professional_profile",
            "facility_profile",
            "pharmacy_profile",
            "partner_profile",
        ):
            return Response(
                {"status": "error", "message": "Unsupported profile type."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if getattr(user, profile_type, None) is not None:
            return Response(
                {
                    "status": "error",
                    "message": "You already have this profile.",
                    "profile_id": str(getattr(user, profile_type).id),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Identity is fixed to the signed-in account; never trust a re-typed
        # email/phone in add-mode.
        phone = str(user.phone_number or "")

        if profile_type == "professional_profile":
            self._require(data, "profession")
            profession = get_object_or_404(Profession, id=data["profession"])
            profile = ProfessionalProfile.objects.create(
                user=user,
                profession=profession,
                is_student=data.get("is_student", False),
            )
            serializer_cls = ProfessionalProfileSerializer

        elif profile_type == "pharmacy_profile":
            self._require(
                data, "pharmacy_name", "pharmacy_license", "license_expiry_date", "address"
            )
            profile = PharmacyProfile.objects.create(
                user=user,
                pharmacy_name=data["pharmacy_name"],
                pharmacy_license=data["pharmacy_license"],
                license_expiry_date=data["license_expiry_date"],
                address=data["address"],
                phone_number=phone,
                email=user.email,
            )
            serializer_cls = PharmacyProfileSerializer

        elif profile_type == "facility_profile":
            self._require(
                data, "facility_name", "facility_type", "address", "region", "district"
            )
            profile = FacilityProfile.objects.create(
                user=user,
                phone_number=phone,
                email=user.email,
                name=data["facility_name"],
                facility_type=data["facility_type"],
                latitude=data.get("latitude"),
                longitude=data.get("longitude"),
                address=data["address"],
                region=data["region"],
                district=data["district"],
            )
            serializer_cls = FacilityProfileSerializer

        else:  # partner_profile
            from partners.models import PartnerProfile
            from partners.serializers import PartnerProfileSerializer

            self._require(data, "organization_name", "organization_type", "partnership_type")
            profile = PartnerProfile.objects.create(
                user=user,
                organization_name=data["organization_name"],
                organization_type=data["organization_type"],
                organization_size=data.get("organization_size", ""),
                registration_number=data.get("registration_number", ""),
                partnership_type=data["partnership_type"],
                organization_phone=phone,
                organization_email=user.email,
                organization_address=data.get("organization_address", ""),
                region=data.get("region", ""),
                district=data.get("district", ""),
                website=data.get("website", "") or None,
                contact_person_name=data.get("contact_person_name", ""),
                contact_person_title=data.get("contact_person_title", ""),
                contact_person_phone=data.get("contact_person_phone") or None,
                is_verified=False,
            )
            serializer_cls = PartnerProfileSerializer

        user.default_profile = profile.id
        user.save()

        return Response(
            serializer_cls(profile, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
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

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[permissions.IsAuthenticated],
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
            # PlatformProfileSerializer.to_representation detects the user's
            # platform profile from its relations, so pass the user directly.
            serializer = serializers.PlatformProfileSerializer(user)
            return Response(serializer.data)
        except Exception:
            return Response(
                {"error": "Profile not found"}, status=status.HTTP_404_NOT_FOUND
            )

    def patch(self, request):
        """Update the current user's platform-specific profile.

        The platform is derived from whichever profile relation the user
        actually has (CustomUser has no ``platform`` field), and we only ever
        update ``request.user``'s own profile.
        """
        user = request.user

        # Map each platform profile relation to its serializer (lazy imports to
        # avoid circular dependencies).
        if hasattr(user, "community_profile"):
            from communities.serializers import OrganizationSerializer

            serializer = OrganizationSerializer(
                user.community_profile, data=request.data, partial=True
            )
        elif hasattr(user, "professional_profile"):
            from professionals.serializers import ProfessionalProfileSerializer

            serializer = ProfessionalProfileSerializer(
                user.professional_profile, data=request.data, partial=True
            )
        elif hasattr(user, "facility_profile"):
            from facilities.serializers import FacilityProfileSerializer

            serializer = FacilityProfileSerializer(
                user.facility_profile, data=request.data, partial=True
            )
        elif hasattr(user, "partner_profile"):
            from partners.serializers import PartnerProfileSerializer

            serializer = PartnerProfileSerializer(
                user.partner_profile, data=request.data, partial=True
            )
        elif hasattr(user, "pharmacy_profile"):
            from pharmacies.serializers import PharmacyProfileSerializer

            serializer = PharmacyProfileSerializer(
                user.pharmacy_profile, data=request.data, partial=True
            )
        elif hasattr(user, "patient_profile"):
            from patients.serializers import PatientProfileSerializer

            serializer = PatientProfileSerializer(
                user.patient_profile, data=request.data, partial=True
            )
        else:
            return Response(
                {"error": "Profile not found"}, status=status.HTTP_404_NOT_FOUND
            )

        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class SetDefaultProfileView(APIView):
    """
    Set default profile for current user
    """

    serializer_class = serializers.SetDefaultProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        profile_id = str(serializer.validated_data.get("profile_id"))

        user = request.user

        # The target must be one of the user's own profile ids OR an org they
        # are an active staff member of — never an arbitrary id.
        allowed_ids = set()
        for rel in (
            "community_profile",
            "professional_profile",
            "facility_profile",
            "partner_profile",
            "pharmacy_profile",
            "patient_profile",
        ):
            obj = getattr(user, rel, None)
            if obj is not None:
                allowed_ids.add(str(obj.id))
        facility_staff = getattr(user, "facility_staff", None)
        if facility_staff is not None:
            allowed_ids.add(str(facility_staff.facility_id))
        try:
            from communities.models import Staff

            allowed_ids.update(
                str(org_id)
                for org_id in Staff.objects.filter(
                    user_account=user, status=Staff.Status.ACTIVE
                ).values_list("organization_id", flat=True)
            )
        except Exception:
            pass

        if profile_id not in allowed_ids:
            return Response(
                data={
                    "status": "error",
                    "message": "You cannot switch to that profile or organization.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        user.default_profile = profile_id
        user.save()
        return Response(
            data={"status": "success", "message": "Default profile set"},
            status=status.HTTP_200_OK,
        )


class ChangePasswordView(APIView):
    """
    Change password for current authenticated user
    """

    serializer_class = serializers.PasswordChangeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = self.serializer_class(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {"message": "Password changed successfully"}, status=status.HTTP_200_OK
        )


def _client_ip(request):
    """Best-effort client IP for audit logging."""
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR") or "0.0.0.0"


class RequestPasswordResetView(APIView):
    """
    Start the forgot-password flow. Accepts an email and, if a matching account
    exists, emails a single-use, time-limited reset link to it.

    Security: always returns the same generic success response regardless of
    whether the email is registered, to prevent account enumeration.
    """

    serializer_class = serializers.ForgotPasswordSerializer
    permission_classes = [permissions.AllowAny]
    throttle_scope = "password_reset"

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]

        user = CustomUser.objects.filter(email__iexact=email).first()
        if user is not None:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            expiry_minutes = settings.PASSWORD_RESET_TIMEOUT // 60
            reset_url = (
                f"{settings.FRONTEND_URL}/reset-password?uid={uid}&token={token}"
            )

            generic_send_mail(
                recipient=user.email,
                title="Reset your BridgeCare password",
                payload={
                    "user_name": (user.get_full_name() or "").strip() or user.email,
                    "reset_url": reset_url,
                    "expiry_minutes": expiry_minutes,
                },
                email_type="password_reset",
            )

            try:
                AuthenticationAudit.objects.create(
                    user=user,
                    action="password_reset",
                    ip_address=_client_ip(request),
                    user_agent=request.META.get("HTTP_USER_AGENT", ""),
                    success=True,
                    details={"stage": "requested"},
                    endpoint=request.path,
                    method=request.method,
                    response_code=status.HTTP_200_OK,
                )
            except Exception:
                # Audit logging must never break the user-facing flow.
                pass

        return Response(
            data={
                "status": "success",
                "message": (
                    "If an account exists for that email, a password reset link "
                    "has been sent."
                ),
            },
            status=status.HTTP_200_OK,
        )


class ResetPasswordConfirmView(APIView):
    """
    Complete the forgot-password flow: validate the uid + token from the reset
    link and set the user's new password. Token validation is delegated to the
    serializer (Django's default_token_generator).
    """

    serializer_class = serializers.ResetPasswordSerializer
    permission_classes = [permissions.AllowAny]
    throttle_scope = "password_reset"

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        try:
            AuthenticationAudit.objects.create(
                user=user,
                action="password_reset",
                ip_address=_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
                success=True,
                details={"stage": "completed"},
                endpoint=request.path,
                method=request.method,
                response_code=status.HTTP_200_OK,
            )
        except Exception:
            pass

        return Response(
            data={
                "status": "success",
                "message": "Password has been reset successfully. You can now log in.",
            },
            status=status.HTTP_200_OK,
        )


class AddressViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing addresses
    """

    queryset = Address.objects.all()
    serializer_class = serializers.AddressSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["user", "label", "city", "region"]
    ordering_fields = ["created_at", "updated_at"]
    ordering = ["-created_at"]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CSRFTokenView(APIView):
    """Sets and returns the CSRF cookie. Call this on app startup."""

    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request):
        token = get_token(request)
        return Response({"csrfToken": token})
