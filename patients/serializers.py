from rest_framework import serializers
from .models import PatientProfile
from accounts.serializers import UserSerializer


class PatientProfileSerializer(serializers.ModelSerializer):
    """
    Patient profile serializer
    """
    user = UserSerializer(read_only=True)
    bmi = serializers.FloatField(read_only=True)
    preferred_pharmacy_name = serializers.SerializerMethodField()

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
            "preferred_payment_method",
            "preferred_language",
            "preferred_consultation_type",
            "notification_preferences",
            "medical_history",
            "allergies",
            "current_medications",
            "home_address",
            "work_address",
            "preferred_pharmacy",
            "preferred_pharmacy_name",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def get_preferred_pharmacy_name(self, obj):
        if obj.preferred_pharmacy:
            return obj.preferred_pharmacy.pharmacy_name
        return None

