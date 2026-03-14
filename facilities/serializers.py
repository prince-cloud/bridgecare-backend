from rest_framework import serializers
from .models import FacilityProfile, Locum, FacilityStaff
from accounts.serializers import UserSerializer


class FacilityProfileSerializer(serializers.ModelSerializer):
    """
    Facility profile serializer
    """

    user = UserSerializer(read_only=True)

    class Meta:
        model = FacilityProfile
        fields = (
            "id",
            "user",
            "name",
            "facility_type",
            "address",
            "district",
            "region",
            "phone_number",
            "email",
            "latitude",
            "longitude",
            "slug",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "slug", "created_at", "updated_at")


class LocumSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = Locum
        fields = (
            "id",
            "user",
            "full_name",
            "profession",
            "phone_number",
            "email",
            "license_number",
            "years_of_experience",
            "is_available",
            "region",
            "district",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class FacilityStaffSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    facility_name = serializers.CharField(source="facility.name", read_only=True)

    class Meta:
        model = FacilityStaff
        fields = (
            "id",
            "user",
            "facility",
            "facility_name",
            "full_name",
            "profession",
            "employee_id",
            "position",
            "department",
            "phone_number",
            "email",
            "hire_date",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")
