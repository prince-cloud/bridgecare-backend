from django.contrib.admin.models import LogEntry
from django.contrib.admin.models import ADDITION, CHANGE, DELETION
from rest_framework.views import APIView
from rest_framework.response import Response

from .coverage import MODEL_TO_RESOURCE
from .permissions import IsPlatformAdmin

ACTION_FLAGS = {ADDITION: "add", CHANGE: "change", DELETION: "delete"}


def _portal_permissions(user):
    """The user's effective model permissions in the portal's format
    (`app.model.action`), derived from Django groups + direct assignments."""
    perms = []
    for perm in user.get_all_permissions():
        try:
            app_label, codename = perm.split(".", 1)
            action, model_name = codename.split("_", 1)
        except ValueError:
            continue
        if action in {"view", "add", "change", "delete"}:
            perms.append(f"{app_label}.{model_name}.{action}")
    return sorted(set(perms))


class AdminMeView(APIView):
    """Identity of the signed-in operator — used by the admin app's auth gate."""

    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        u = request.user
        return Response(
            {
                "id": str(u.id),
                "email": u.email,
                "name": (u.get_full_name() or "").strip() or u.email,
                "is_staff": u.is_staff,
                "is_superuser": u.is_superuser,
                "is_admin": u.is_superuser,
                "permissions": [] if u.is_superuser else _portal_permissions(u),
                "groups": [g.name for g in u.groups.all()],
            }
        )


class RecentActionsView(APIView):
    """The signed-in operator's own recent audit trail (django.admin LogEntry),
    powering the dashboard's Recent actions panel."""

    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        limit = min(int(request.query_params.get("limit", 10) or 10), 50)
        entries = (
            LogEntry.objects.filter(user=request.user)
            .select_related("user", "content_type")
            .order_by("-action_time")[:limit]
        )
        return Response(
            [
                {
                    "id": str(e.id),
                    "action_time": e.action_time.isoformat(),
                    "user_name": str(e.user),
                    "resource": MODEL_TO_RESOURCE.get(e.content_type.model, e.content_type.model),
                    "object_id": str(e.object_id),
                    "object_repr": e.object_repr,
                    "action": ACTION_FLAGS.get(e.action_flag, "change"),
                    "message": e.get_change_message(),
                }
                for e in entries
            ]
        )
