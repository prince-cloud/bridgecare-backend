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
            "pharmacy_type",
            "address",
            "district",
            "region",
            "latitude",
            "longitude",
            "phone_number",
            "email",
            "website",
            "services_offered",
            "delivery_available",
            "delivery_radius",
            "operating_hours",
            "pharmacist_license",
            "staff_count",
            "payment_methods",
            "insurance_accepted",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

