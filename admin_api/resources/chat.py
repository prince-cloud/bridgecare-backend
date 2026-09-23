"""Admin API resources for the chat app (read-only oversight)."""
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.response import Response

from chat.models import Chat, Message, AIChatSession, AIChatMessage, AIAbuseEvent
from chat.serializers import (
    ChatSerializer,
    MessageSerializer,
    AIChatSessionSerializer,
    AIChatSessionDetailSerializer,
    AIChatMessageSerializer,
)
from admin_api.base import AdminReadOnlyViewSet


class AIAbuseEventAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIAbuseEvent
        fields = "__all__"
        read_only_fields = ("id", "created_at")


class ChatAdminViewSet(AdminReadOnlyViewSet):
    queryset = Chat.objects.select_related("patient", "professional").all()
    serializer_class = ChatSerializer
    search_fields = ["patient__user__email", "professional__user__email"]
    filterset_fields = ["patient", "professional"]
    ordering_fields = ["created_at"]
    facet_fields = ["patient", "professional"]


class MessageAdminViewSet(AdminReadOnlyViewSet):
    queryset = Message.objects.select_related("chat").all()
    serializer_class = MessageSerializer
    search_fields = ["content"]
    filterset_fields = ["chat", "is_read"]
    ordering_fields = ["created_at"]
    facet_fields = ["chat", "is_read"]


class AIChatSessionAdminViewSet(AdminReadOnlyViewSet):
    queryset = AIChatSession.objects.select_related("user").all()
    serializer_class = AIChatSessionSerializer
    search_fields = ["title", "user__email"]
    filterset_fields = ["is_active", "user"]
    ordering_fields = ["created_at"]
    facet_fields = ["user", "is_active"]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return AIChatSessionDetailSerializer
        return AIChatSessionSerializer

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        s = self.get_object(); s.is_active = False; s.save()
        return Response(AIChatSessionSerializer(s).data)


class AIChatMessageAdminViewSet(AdminReadOnlyViewSet):
    queryset = AIChatMessage.objects.select_related("session").all()
    serializer_class = AIChatMessageSerializer
    search_fields = ["content"]
    filterset_fields = ["session", "message_type"]
    ordering_fields = ["created_at"]
    facet_fields = ["session", "message_type"]


class AIAbuseEventAdminViewSet(AdminReadOnlyViewSet):
    queryset = AIAbuseEvent.objects.select_related("user").all()
    serializer_class = AIAbuseEventAdminSerializer
    search_fields = ["ip_address"]
    filterset_fields = ["event_type", "user"]
    ordering_fields = ["created_at"]
    facet_fields = ["event_type", "user", "strikes"]


def register(router):
    router.register("chats", ChatAdminViewSet, basename="admin-chats")
    router.register("chat-messages", MessageAdminViewSet, basename="admin-chat-messages")
    router.register("ai-sessions", AIChatSessionAdminViewSet, basename="admin-ai-sessions")
    router.register("ai-messages", AIChatMessageAdminViewSet, basename="admin-ai-messages")
    router.register("ai-abuse-events", AIAbuseEventAdminViewSet, basename="admin-ai-abuse-events")


EXTRA_URLS = []
