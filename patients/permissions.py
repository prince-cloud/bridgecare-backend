from rest_framework import permissions


class HealthProfessionalRequired(permissions.BasePermission):
    """
    Permission class to check if the user has a health professional profile.
    """

    message = "You must have a health professional profile to access this resource."

    def has_permission(self, request, view):
        """
        Check if the user has a professional profile.
        """
        if not request.user or not request.user.is_authenticated:
            return False

        return hasattr(request.user, "professional_profile")
