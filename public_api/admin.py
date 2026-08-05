from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import ContactEnquiry


@admin.register(ContactEnquiry)
class ContactEnquiryAdmin(ModelAdmin):
    """
    Queue for public contact-form submissions.

    `notification_sent` is the tell-tale: a run of False rows means the mail
    provider is failing, not that nobody is writing in.
    """

    list_display = [
        "created_at",
        "full_name",
        "email",
        "company_name",
        "status",
        "notification_sent",
    ]
    list_filter = ["status", "notification_sent", "created_at"]
    search_fields = ["full_name", "email", "company_name", "message", "phone_number"]
    list_editable = ["status"]
    readonly_fields = [
        "full_name",
        "company_name",
        "email",
        "phone_number",
        "message",
        "notification_sent",
        "ip_address",
        "user_agent",
        "created_at",
        "updated_at",
    ]
    ordering = ["-created_at"]

    def has_add_permission(self, request):
        return False
