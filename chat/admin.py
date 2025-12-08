from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import Chat, Message


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
