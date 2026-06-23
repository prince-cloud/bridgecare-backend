from rest_framework import permissions


def user_org_relationship(user, organization_id):
    """
    Describe how ``user`` relates to the org identified by ``organization_id``.

    Returns ("owner", Organization) if the user owns it (their community_profile),
    ("staff", Organization) if they have an ACTIVE staff membership, otherwise
    (None, None). This is the single source of truth for "can this user act in
    this organization" and underpins both ownership and staff access.
    """
    from .models import Staff

    if not user or not user.is_authenticated or not organization_id:
        return None, None

    org = getattr(user, "community_profile", None)
    if org is not None and str(org.id) == str(organization_id):
        return "owner", org

    membership = (
        Staff.objects.select_related("organization")
        .filter(
            user_account=user,
            organization_id=organization_id,
            status=Staff.Status.ACTIVE,
        )
        .first()
    )
    if membership is not None:
        return "staff", membership.organization

    return None, None


def resolve_member_organization(user, organization_id):
    """Return the Organization if the user is owner or active staff, else None."""
    _, org = user_org_relationship(user, organization_id)
    return org


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


class OrganizationMemberRequired(permissions.BasePermission):
    """
    Allow access if the user is the owner OR an active staff member of the
    organization in the URL (``organization_id``). Use on org-scoped views that
    staff should be able to use.
    """

    message = "You do not have access to this organization."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        organization_id = view.kwargs.get("organization_id")
        relationship, _ = user_org_relationship(request.user, organization_id)
        return relationship is not None
