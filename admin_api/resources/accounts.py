"""Admin API resources for the accounts app (People & Accounts, Security)."""
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.models import (
    CustomUser,
    Address,
    Role,
    UserRole,
    MFADevice,
    LoginSession,
    SecurityEvent,
    AuthenticationAudit,
    DataAccessLog,
)
from accounts.serializers import (
    UserSerializer,
    UserCreateSerializer,
    AddressSerializer,
    RoleSerializer,
    UserRoleSerializer,
    MFADeviceSerializer,
    LoginSessionSerializer,
    SecurityEventSerializer,
    AuthenticationAuditSerializer,
    DataAccessLogSerializer,
)
from admin_api.base import AdminModelViewSet, AdminReadOnlyViewSet


class UserAdminViewSet(AdminModelViewSet):
    queryset = CustomUser.objects.all().order_by("-created_at")
    serializer_class = UserSerializer
    search_fields = ["email", "username", "first_name", "last_name", "phone_number"]
    filterset_fields = ["is_verified", "is_active", "is_staff", "is_superuser", "mfa_enabled"]
    ordering_fields = ["created_at", "last_activity", "email"]

    def get_serializer_class(self):
        if self.action == "create":
            return UserCreateSerializer
        return UserSerializer

    @action(detail=True, methods=["post"])
    def verify(self, request, pk=None):
        user = self.get_object()
        user.is_verified = True
        user.save()
        return Response(UserSerializer(user).data)

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        user = self.get_object()
        user.is_active = True
        user.save()
        return Response(UserSerializer(user).data)

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        user = self.get_object()
        user.is_active = False
        user.save()
        return Response(UserSerializer(user).data)

    @action(detail=True, methods=["post"], url_path="unlock-account")
    def unlock_account(self, request, pk=None):
        user = self.get_object()
        user.login_attempts = 0
        user.account_locked_until = None
        user.save()
        return Response(UserSerializer(user).data)


class AddressAdminViewSet(AdminModelViewSet):
    queryset = Address.objects.select_related("user").all()
    serializer_class = AddressSerializer
    search_fields = ["label", "address", "city", "region"]
    filterset_fields = ["user", "region", "city"]
    ordering_fields = ["created_at", "updated_at"]


class RoleAdminViewSet(AdminModelViewSet):
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    search_fields = ["name", "description"]
    filterset_fields = ["platform", "is_active"]
    ordering_fields = ["name", "created_at"]


class UserRoleAdminViewSet(AdminModelViewSet):
    queryset = UserRole.objects.select_related("user", "role", "facility", "assigned_by").all()
    serializer_class = UserRoleSerializer
    search_fields = ["user__email", "role__name"]
    filterset_fields = ["user", "role", "facility", "is_active"]
    ordering_fields = ["assigned_at", "expires_at"]


class MFADeviceAdminViewSet(AdminReadOnlyViewSet):
    queryset = MFADevice.objects.select_related("user").all()
    serializer_class = MFADeviceSerializer
    search_fields = ["user__email", "device_name"]
    filterset_fields = ["user", "device_type", "is_verified", "is_primary"]
    ordering_fields = ["created_at", "last_used"]


class LoginSessionAdminViewSet(AdminReadOnlyViewSet):
    queryset = LoginSession.objects.select_related("user").all()
    serializer_class = LoginSessionSerializer
    search_fields = ["user__email", "ip_address"]
    filterset_fields = ["user", "is_active"]
    ordering_fields = ["created_at", "last_activity", "expires_at"]


class SecurityEventAdminViewSet(AdminReadOnlyViewSet):
    queryset = SecurityEvent.objects.select_related("user", "resolved_by").all()
    serializer_class = SecurityEventSerializer
    search_fields = ["user__email", "ip_address"]
    filterset_fields = ["event_type", "severity", "is_resolved", "user"]
    ordering_fields = ["timestamp", "severity"]

    @action(detail=True, methods=["post"])
    def resolve(self, request, pk=None):
        from django.utils import timezone

        event = self.get_object()
        event.is_resolved = True
        event.resolved_at = timezone.now()
        event.resolved_by = request.user
        event.save()
        return Response(SecurityEventSerializer(event).data)


class AuthAuditAdminViewSet(AdminReadOnlyViewSet):
    queryset = AuthenticationAudit.objects.select_related("user").all()
    serializer_class = AuthenticationAuditSerializer
    search_fields = ["user__email", "ip_address", "endpoint"]
    filterset_fields = ["action", "success", "user", "platform"]
    ordering_fields = ["timestamp"]


class DataAccessLogAdminViewSet(AdminReadOnlyViewSet):
    queryset = DataAccessLog.objects.select_related("user").all()
    serializer_class = DataAccessLogSerializer
    search_fields = ["user__email", "resource_name", "resource_id"]
    filterset_fields = ["data_type", "access_type", "user", "platform"]
    ordering_fields = ["timestamp"]


def register(router):
    router.register("users", UserAdminViewSet, basename="admin-users")
    router.register("addresses", AddressAdminViewSet, basename="admin-addresses")
    router.register("roles", RoleAdminViewSet, basename="admin-roles")
    router.register("role-assignments", UserRoleAdminViewSet, basename="admin-role-assignments")
    router.register("mfa-devices", MFADeviceAdminViewSet, basename="admin-mfa-devices")
    router.register("login-sessions", LoginSessionAdminViewSet, basename="admin-login-sessions")
    router.register("security-events", SecurityEventAdminViewSet, basename="admin-security-events")
    router.register("auth-audit", AuthAuditAdminViewSet, basename="admin-auth-audit")
    router.register("data-access-logs", DataAccessLogAdminViewSet, basename="admin-data-access-logs")


EXTRA_URLS = []
