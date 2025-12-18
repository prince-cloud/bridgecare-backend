from rest_framework import permissions


class CommunityProfileRequired(permissions.BasePermission):
    """
    Permission class to check if the user has a community profile.
    """

    message = "You must have a community profile to access this resource."

    def has_permission(self, request, view):
        """
        Check if the user has a community profile.
        """
        if not request.user or not request.user.is_authenticated:
            return False

        return hasattr(request.user, "community_profile")
