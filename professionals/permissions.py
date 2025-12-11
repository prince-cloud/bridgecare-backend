from rest_framework import permissions


class ProfessionalProfileRequired(permissions.BasePermission):
    """
    Permission class to check if the user has a professional profile.
    """

    message = "You must have a professional profile to access this resource."

    def has_permission(self, request, view):
        """
        Check if the user has a professional profile.
        """
        if not request.user or not request.user.is_authenticated:
            return False

        return hasattr(request.user, "professional_profile")


# patient profile required
class PatientProfileRequired(permissions.BasePermission):
    """
    Permission class to check if the user has a patient profile.
    """

    message = "You must have a patient profile to access this resource."

    def has_permission(self, request, view):
        """
        Check if the user has a patient profile.
        """
        if not request.user or not request.user.is_authenticated:
            return False

        return hasattr(request.user, "patient_profile")
