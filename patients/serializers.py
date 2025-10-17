from rest_framework import serializers
from .models import PatientProfile
from accounts.serializers import UserSerializer


class PatientProfileSerializer(serializers.ModelSerializer):
    """
    Patient profile serializer
    """

    user = UserSerializer(read_only=True)
    bmi = serializers.FloatField(read_only=True)

    class Meta:
        model = PatientProfile
        fields = (
            "id",
            "user",
            "blood_type",
            "height",
            "weight",
            "bmi",
            "emergency_contact_name",
            "emergency_contact_phone",
            "emergency_contact_relationship",
            "insurance_provider",
            "insurance_number",
            "date_created",
            "last_updated",
        )
        read_only_fields = ("id", "date_created", "last_updated")
