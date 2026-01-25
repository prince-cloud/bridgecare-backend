from rest_framework import permissions


class PharmacyProfileRequired(permissions.BasePermission):
    """
    Permission class to check if the user has a pharmacy profile.
    """

    message = "You must have a pharmacy profile to access this resource."

    def has_permission(self, request, view):
        """
        Check if the user has a pharmacy profile.
        """
        if not request.user or not request.user.is_authenticated:
            return False

        return hasattr(request.user, "pharmacy_profile")
