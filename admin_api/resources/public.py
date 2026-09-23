"""Admin API resources for the public website (contact enquiries)."""
from rest_framework import serializers

from public_api.models import ContactEnquiry
from admin_api.base import AdminModelViewSet


class ContactEnquiryAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactEnquiry
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at", "notification_sent")


class ContactEnquiryAdminViewSet(AdminModelViewSet):
    queryset = ContactEnquiry.objects.all()
    serializer_class = ContactEnquiryAdminSerializer
    search_fields = ["full_name", "email", "company_name", "message"]
    filterset_fields = ["status"]
    ordering_fields = ["created_at"]
    facet_fields = ["status"]


def register(router):
    router.register("contact-enquiries", ContactEnquiryAdminViewSet, basename="admin-contact-enquiries")


EXTRA_URLS = []
