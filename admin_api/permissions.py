from rest_framework import permissions


class IsPlatformAdmin(permissions.BasePermission):
    """
    Access for platform operators only: a logged-in user with is_staff or
    is_superuser. This is the single gate for every admin_api endpoint.
    """

    message = "You must be a platform administrator to access the admin API."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and (user.is_staff or user.is_superuser)
        )
