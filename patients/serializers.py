import datetime
from rest_framework import serializers
from .models import PatientProfile
from accounts.serializers import UserSerializer
from django.utils import timezone


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
            "patient_id",
            "user",
            "first_name",
            "surname",
            "other_names",
            "last_name",
            "gender",
            "email",
            "phone_number",
            "date_of_birth",
            "profile_picture",
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


class PatientProfileListSerializer(serializers.ModelSerializer):
    """
    Patient profile serializer without user field for listing
    """

    age = serializers.SerializerMethodField(read_only=True)

    def get_age(self, obj):
        current_date = timezone.now()
        age = current_date.year - obj.date_of_birth.year if obj.date_of_birth else None
        return age

    class Meta:
        model = PatientProfile
        fields = (
            "id",
            "patient_id",
            "first_name",
            "surname",
            "other_names",
            "last_name",
            "gender",
            "email",
            "phone_number",
            "date_of_birth",
            "profile_picture",
            "age",
        )
        read_only_fields = ("id",)
