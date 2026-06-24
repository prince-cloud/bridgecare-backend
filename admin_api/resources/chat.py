"""Admin API resources for the chat app (read-only oversight)."""
from rest_framework.decorators import action
from rest_framework.response import Response

from chat.models import Chat, AIChatSession
from chat.serializers import (
    ChatSerializer,
    AIChatSessionSerializer,
    AIChatSessionDetailSerializer,
)
from admin_api.base import AdminReadOnlyViewSet


class ChatAdminViewSet(AdminReadOnlyViewSet):
    queryset = Chat.objects.all()
    serializer_class = ChatSerializer
    filterset_fields = ["patient", "professional"]
    ordering_fields = ["created_at"]


class AIChatSessionAdminViewSet(AdminReadOnlyViewSet):
    queryset = AIChatSession.objects.select_related("user").all()
    serializer_class = AIChatSessionSerializer
    filterset_fields = ["is_active", "user"]
    ordering_fields = ["created_at"]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return AIChatSessionDetailSerializer
        return AIChatSessionSerializer

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        s = self.get_object(); s.is_active = False; s.save()
        return Response(AIChatSessionSerializer(s).data)


def register(router):
    router.register("chats", ChatAdminViewSet, basename="admin-chats")
    router.register("ai-sessions", AIChatSessionAdminViewSet, basename="admin-ai-sessions")


EXTRA_URLS = []
