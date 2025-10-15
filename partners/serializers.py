from rest_framework import serializers
from .models import PartnerProfile
from accounts.serializers import UserSerializer


class PartnerProfileSerializer(serializers.ModelSerializer):
    """
    Partner profile serializer
    """
    user = UserSerializer(read_only=True)

    class Meta:
        model = PartnerProfile
        fields = (
            "id",
            "user",
            "organization_name",
            "organization_type",
            "organization_size",
            "organization_phone",
            "organization_email",
            "organization_address",
            "website",
            "partnership_type",
            "partnership_status",
            "partnership_start_date",
            "partnership_end_date",
            "api_access_level",
            "can_access_analytics",
            "can_manage_subsidies",
            "can_view_patient_data",
            "contact_person_name",
            "contact_person_title",
            "contact_person_phone",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

