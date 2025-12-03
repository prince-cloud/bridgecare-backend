from rest_framework.routers import DefaultRouter
from django.urls import path
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
router.register("users", views.UserViewSet, basename="user")
router.register("profiles", views.UserProfileViewSet, basename="userprofile")
router.register("roles", views.RoleViewSet, basename="role")
router.register("user-roles", views.UserRoleViewSet, basename="userrole")

urlpatterns = [
    # Legacy endpoints for backward compatibility
    path(
        "account-profile/", views.AccountProfileView.as_view(), name="account_profile"
    ),
    path(
        "set-default-profile/",
        views.SetDefaultProfileView.as_view(),
        name="set_default_profile",
    ),
    path(
        "change-password/",
        views.ChangePasswordView.as_view(),
        name="change_password",
    ),
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
    path("validate-email/", views.ValidateEmailView.as_view(), name="validate_email"),
    path(
        "validate-phone-number/",
        views.ValidatePhoneNumberView.as_view(),
        name="validate_phone_number",
    ),
    path(
        "validate-email-and-phone-number/",
        views.ValidateEmailAndPhoneNumberView.as_view(),
        name="validate_email_and_phone_number",
    ),
    path(
        "verify-email-otp/",
        views.VerifyEmailOTPView.as_view(),
        name="verify_email_otp",
    ),
    path(
        "verify-phone-number-otp/",
        views.VerifyPhoneNumberOTPView.as_view(),
        name="verify_phone_number_otp",
    ),
    # organization endpoints
    path(
        "create-organization-user/",
        views.CreateOrganizationUserView.as_view(),
        name="create_organization_user",
    ),
]

# Include router URLs
urlpatterns += router.urls
