from rest_framework import serializers
from .models import (
    ProfessionalProfile,
    Profession,
    Specialization,
    LicenceIssueAuthority,
)
from accounts.serializers import UserSerializer


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
    """
    Specialization serializer
    """

    class Meta:
        model = Specialization
        fields = (
            "id",
            "name",
            "description",
        )


class LicenceIssueAuthoritySerializer(serializers.ModelSerializer):
    """
    Licence issue authority serializer
    """

    class Meta:
        model = LicenceIssueAuthority
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
    # is_profile_completed = serializers.BooleanField(read_only=True)

    # def get_is_profile_completed(self, obj):
    #     if (
    #         obj.education_status
    #         and obj.education_status__in[
    #             ProfessionalProfile.EducationStatus.IN_SCHOOL,
    #             ProfessionalProfile.EducationStatus.COMPLETED,
    #         ]
    #         and not obj.education_histories.exists()
    #     ):
    #         return False
    #     return obj.education_status and obj.profession

    class Meta:
        model = ProfessionalProfile
        fields = (
            "id",
            "user",
            "education_status",
            "profession",
            "specialization",
            "facility_affiliation",
            "license_number",
            "license_expiry_date",
            "license_issuing_authority",
            "years_of_experience",
            "is_active",
            "is_profile_completed",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")
