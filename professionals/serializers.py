from rest_framework import serializers
from .models import ProfessionalProfile
from accounts.serializers import UserSerializer


class ProfessionalProfileSerializer(serializers.ModelSerializer):
    """
    Professional profile serializer
    """
    user = UserSerializer(read_only=True)
    is_license_valid = serializers.BooleanField(read_only=True)

    class Meta:
        model = ProfessionalProfile
        fields = (
            "id",
            "user",
            "practice_type",
            "years_of_experience",
            "education_background",
            "license_number",
            "license_issuing_body",
            "license_expiry_date",
            "is_license_valid",
            "certifications",
            "availability_schedule",
            "preferred_working_hours",
            "travel_radius",
            "hourly_rate",
            "currency",
            "specializations",
            "languages_spoken",
            "emergency_contact",
            "emergency_phone",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

