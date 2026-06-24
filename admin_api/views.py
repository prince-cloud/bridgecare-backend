from rest_framework.views import APIView
from rest_framework.response import Response

from .permissions import IsPlatformAdmin


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
                "is_admin": True,
            }
        )
