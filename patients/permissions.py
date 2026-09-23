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


class PatientReadOrClinicianWrite(permissions.BasePermission):
    """
    Any signed-in user may read; only professionals and facilities may write.

    The record viewsets already scope their querysets with `patients.access`,
    which includes the patient's own profile. The permission was the only
    thing stopping a patient from reading their own vitals, prescriptions,
    diagnoses, allergies, notes and history: the patient dashboard called
    these endpoints and got 403, so the health tiles stayed blank
    (tech report 18.08.2026, item 1.2).
    """

    message = "You must have a health professional or facility profile to change this resource."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        return ProfessionalOrFacilityRequired().has_permission(request, view)


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
