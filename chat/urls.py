from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register("chats", views.ChatViewSet, basename="chat")
router.register(
    "ai-chat-sessions",
    views.AIChatSessionViewSet,
    basename="ai-chat-session",
)


urlpatterns = [
    path("ai-agent/", views.AIAgentView.as_view(), name="ai-agent"),
    path("", include(router.urls)),
]
