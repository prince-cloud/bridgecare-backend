from rest_framework import permissions


class HealthProfessionalRequired(permissions.BasePermission):
    """
    Permission class to check if the user has a health professional profile.
    """

    message = "You must have a health professional profile to access this resource."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return hasattr(request.user, "professional_profile")


class ProfessionalOrFacilityRequired(permissions.BasePermission):
    """Allows health professionals AND facility admins/staff."""

    message = "You must have a health professional or facility profile to access this resource."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if hasattr(request.user, "professional_profile"):
            return True
        # Lazy import to avoid circular dependency
        from facilities.views import get_facility_for_user
        return get_facility_for_user(request.user) is not None
