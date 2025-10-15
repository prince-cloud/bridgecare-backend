from rest_framework.routers import DefaultRouter
from django.urls import path, include
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)
from . import views
from dj_rest_auth.views import LoginView

app_name = "accounts"

# Create router for all ViewSets
router = DefaultRouter()

# Register all ViewSets
router.register(r"users", views.UserViewSet, basename="user")
router.register(r"facilities", views.FacilityViewSet, basename="facility")
router.register(r"profiles", views.UserProfileViewSet, basename="userprofile")
router.register(
    r"community-profiles", views.CommunityProfileViewSet, basename="communityprofile"
)
router.register(
    r"professional-profiles",
    views.ProfessionalProfileViewSet,
    basename="professionalprofile",
)
router.register(
    r"facility-profiles", views.FacilityProfileViewSet, basename="facilityprofile"
)
router.register(
    r"partner-profiles", views.PartnerProfileViewSet, basename="partnerprofile"
)
router.register(
    r"pharmacy-profiles", views.PharmacyProfileViewSet, basename="pharmacyprofile"
)
router.register(
    r"patient-profiles", views.PatientProfileViewSet, basename="patientprofile"
)
router.register(r"roles", views.RoleViewSet, basename="role")
router.register(r"user-roles", views.UserRoleViewSet, basename="userrole")
router.register(r"mfa-devices", views.MFADeviceViewSet, basename="mfadevice")
router.register(r"login-sessions", views.LoginSessionViewSet, basename="loginsession")
router.register(
    r"security-events", views.SecurityEventViewSet, basename="securityevent"
)
router.register(
    r"auth-audit", views.AuthenticationAuditViewSet, basename="authenticationaudit"
)
router.register(
    r"data-access-logs", views.DataAccessLogViewSet, basename="dataaccesslog"
)

# General user & service request endpoints
router.register(r"guest-users", views.GuestUserViewSet, basename="guestuser")
router.register(r"locum-requests", views.LocumRequestViewSet, basename="locumrequest")
router.register(
    r"prescription-requests",
    views.PrescriptionRequestViewSet,
    basename="prescriptionrequest",
)
router.register(
    r"appointment-requests",
    views.AppointmentRequestViewSet,
    basename="appointmentrequest",
)
router.register(
    r"event-registrations",
    views.EventRegistrationViewSet,
    basename="eventregistration",
)

urlpatterns = [
    # Legacy endpoints for backward compatibility
    path("profile/", views.ProfileView.as_view(), name="profile"),
    path(
        "platform-profile/",
        views.PlatformProfileView.as_view(),
        name="platform-profile",
    ),
    # Authentication endpoints
    path("login/", LoginView.as_view(), name="login"),
    path("token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("token/verify/", TokenVerifyView.as_view(), name="token_verify"),
]

# Include router URLs
urlpatterns += router.urls
