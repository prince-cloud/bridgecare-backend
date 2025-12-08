from rest_framework import permissions


class HealthProfessionalRequired(permissions.BasePermission):
    """
    Permission class to check if the user has a health professional profile.
    """

    message = "You must have a health professional or patient profile to access this resource."

    def has_permission(self, request, view):
        """
        Check if the user has a professional or patient profile.
        """
        if not request.user or not request.user.is_authenticated:
            return False

        return hasattr(request.user, "professional_profile") or hasattr(
            request.user, "patient_profile"
        )
