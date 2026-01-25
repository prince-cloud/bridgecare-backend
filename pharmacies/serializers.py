from rest_framework import serializers
from .models import PharmacyProfile
from accounts.serializers import UserSerializer


class PharmacyProfileSerializer(serializers.ModelSerializer):
    """
    Pharmacy profile serializer
    """

    user = UserSerializer(read_only=True)

    class Meta:
        model = PharmacyProfile
        fields = (
            "id",
            "user",
            "pharmacy_name",
            "pharmacy_license",
            "license_expiry_date",
            "address",
            "district",
            "region",
            "latitude",
            "longitude",
            "phone_number",
            "email",
            "website",
            "delivery_available",
            "delivery_radius",
            "pharmacist_license",
            "license_expiry_date",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")
