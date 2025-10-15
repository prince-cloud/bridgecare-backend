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
router.register(r"profiles", views.UserProfileViewSet, basename="userprofile")
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
