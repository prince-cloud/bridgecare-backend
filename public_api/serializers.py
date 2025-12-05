from rest_framework import serializers
from accounts.serializers import UserSerializer
from communities import models as community_models
from professionals.models import Profession, ProfessionalProfile, Specialization


class LocumJobRoleSerializer(serializers.ModelSerializer):
    """
    Serializer for locum job roles
    """

    class Meta:
        model = community_models.LocumJobRole
        fields = (
            "id",
            "name",
        )


class LocumJobSerializer(serializers.ModelSerializer):
    """
    Serializer for locum jobs
    """

    role_name = serializers.CharField(source="role.name", read_only=True)
    organization_name = serializers.CharField(
        source="organization.organization_name", read_only=True
    )
    organization_type = serializers.CharField(
        source="organization.organization_type", read_only=True
    )
    renumeration_display = serializers.SerializerMethodField()

    class Meta:
        model = community_models.LocumJob
        fields = (
            "id",
            "role",
            "role_name",
            "title",
            "organization",
            "organization_name",
            "organization_type",
            "description",
            "requirements",
            "location",
            "title_image",
            "renumeration",
            "renumeration_frequency",
            "renumeration_display",
            "slug",
            "date_created",
            "last_updated",
        )
        read_only_fields = ("id", "date_created", "last_updated")

    def get_renumeration_display(self, obj):
        """Format renumeration with frequency"""
        return f"{obj.renumeration} per {obj.renumeration_frequency}"


class ProfessionsSerializer(serializers.ModelSerializer):
    """
    Professions serializer
    """

    class Meta:
        model = Profession
        fields = (
            "id",
            "name",
            "description",
        )


class SpecializationSerializer(serializers.ModelSerializer):

    class Meta:
        model = Specialization
        fields = (
            "id",
            "name",
            "description",
        )


class ProfessionalProfileSerializer(serializers.ModelSerializer):
    """
    Professional profile serializer
    """

    user = UserSerializer(read_only=True)
    profession = ProfessionsSerializer(read_only=True)
    specialization = SpecializationSerializer(read_only=True)

    class Meta:
        model = ProfessionalProfile
        fields = (
            "id",
            "user",
            "education_status",
            "profession",
            "specialization",
            "facility_affiliation",
            "license_issuing_authority",
            "years_of_experience",
            "is_profile_completed",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")
