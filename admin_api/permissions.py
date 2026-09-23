from django.conf import settings
from rest_framework import permissions


class IsPlatformAdmin(permissions.BasePermission):
    """
    Access for platform operators only: a logged-in user with is_staff or
    is_superuser. This is the outer gate for every admin_api endpoint.
    """

    message = "You must be a platform administrator to access the admin API."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and (user.is_staff or user.is_superuser)
        )


class AdminModelPermission(permissions.BasePermission):
    """
    Per-model RBAC, mirroring the Django admin: staff users need the model
    permission matching the action (view/add/change/delete). Superusers
    bypass it automatically (has_perm always True for them).

    Enabled by default; set ADMIN_API_REQUIRE_MODEL_PERMS=false to fall back
    to platform-admin-only gating while migrating people into groups.
    """

    message = "You don't have permission to perform this action."

    def has_permission(self, request, view):
        if not getattr(settings, "ADMIN_API_REQUIRE_MODEL_PERMS", True):
            return True
        required = getattr(view, "required_permission", None)
        if not required:
            return True
        return bool(request.user and request.user.has_perm(required))
