from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import AIAbuseEvent, Chat, Message


@admin.register(Chat)
class ChatAdmin(ModelAdmin):
    list_display = ["id", "patient", "professional", "created_at", "updated_at"]
    list_filter = ["created_at", "updated_at"]
    search_fields = ["patient__patient_id", "professional__user__email"]
    readonly_fields = ["id", "created_at", "updated_at"]


@admin.register(Message)
class MessageAdmin(ModelAdmin):
    list_display = [
        "id",
        "chat",
        "get_sender",
        "get_content_preview",
        "is_read",
        "created_at",
    ]
    list_filter = ["is_read", "created_at"]
    search_fields = ["chat__patient__patient_id", "chat__professional__user__email"]
    readonly_fields = ["id", "created_at", "get_full_content"]

    def get_sender(self, obj):
        if obj.patient:
            return f"Patient: {obj.patient.patient_id}"
        elif obj.provider:
            return f"Professional: {obj.provider.user.email}"
        return "Unknown"

    get_sender.short_description = "Sender"

    def get_content_preview(self, obj):
        """Show content preview"""
        content = obj.content
        return content[:50] + "..." if len(content) > 50 else content

    get_content_preview.short_description = "Content Preview"

    def get_full_content(self, obj):
        """Show full content"""
        return obj.content

    get_full_content.short_description = "Full Content"


@admin.register(AIAbuseEvent)
class AIAbuseEventAdmin(ModelAdmin):
    """
    Visibility into attempts against the public AI assistant.

    Read-only: this is an evidence trail, not something an operator edits.
    """

    list_display = [
        "created_at",
        "event_type",
        "ip_address",
        "user",
        "strikes",
        "get_prompt_preview",
    ]
    list_filter = ["event_type", "created_at"]
    search_fields = ["ip_address", "user__email", "prompt", "response"]
    readonly_fields = [
        "user",
        "ip_address",
        "event_type",
        "prompt",
        "response",
        "matched_patterns",
        "strikes",
        "created_at",
    ]
    ordering = ["-created_at"]

    def get_prompt_preview(self, obj):
        return (obj.prompt[:80] + "...") if len(obj.prompt) > 80 else obj.prompt

    get_prompt_preview.short_description = "Prompt"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
