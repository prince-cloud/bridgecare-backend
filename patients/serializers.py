from rest_framework import serializers
from .models import (
    Allergy,
    Diagnosis,
    MedicalHistory,
    Notes,
    PatientProfile,
    Prescription,
    Visitation,
    Vitals,
)
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


class VisitationSerializer(serializers.ModelSerializer):
    """
    Visitation serializer
    """

    class Meta:
        model = Visitation
        fields = (
            "id",
            "patient",
            "title",
            "description",
            "date_created",
            "last_updated",
        )
        read_only_fields = (
            "id",
            "date_created",
            "last_updated",
        )


class DiagnosisSerializer(serializers.ModelSerializer):
    """
    Diagnosis serializer
    """

    class Meta:
        model = Diagnosis
        fields = (
            "id",
            "visitation",
            "diagnosis",
        )

        read_only_fields = (
            "id",
            "date_created",
            "last_updated",
        )


class VitalsSerializer(serializers.ModelSerializer):
    """
    Vitals serializer
    """

    class Meta:
        model = Vitals
        fields = (
            "id",
            "visitation",
            "blood_pressure",
            "heart_rate",
            "respiratory_rate",
            "temperature",
            "height",
            "weight",
            "bmi",
            "custom_vitals",
            "date_created",
            "last_updated",
        )

        read_only_fields = (
            "id",
            "date_created",
            "last_updated",
        )


class PrescriptionSerializer(serializers.ModelSerializer):
    """
    Prescription serializer
    """

    class Meta:
        model = Prescription
        fields = (
            "id",
            "visitation",
            "medication",
            "dosage",
            "frequency",
            "duration",
            "instructions",
            "date_created",
            "last_updated",
        )

        read_only_fields = (
            "id",
            "date_created",
            "last_updated",
        )


class AllergySerializer(serializers.ModelSerializer):
    """
    Allergy serializer
    """

    class Meta:
        model = Allergy
        fields = (
            "id",
            "patient",
            "allergy",
            "allergy_severity",
            "date_created",
            "last_updated",
        )

        read_only_fields = (
            "id",
            "date_created",
            "last_updated",
        )


class NotesSerializer(serializers.ModelSerializer):
    """
    Notes serializer
    """

    class Meta:
        model = Notes
        fields = (
            "id",
            "visitation",
            "note",
        )

        read_only_fields = (
            "id",
            "date_created",
            "last_updated",
        )


class MedicalHistorySerializer(serializers.ModelSerializer):
    """
    Medical history serializer
    """

    class Meta:
        model = MedicalHistory
        fields = (
            "id",
            "patient",
            "history_type",
            "name",
            "date_created",
            "last_updated",
        )

        read_only_fields = (
            "id",
            "date_created",
            "last_updated",
        )


class VisitationDetailSerializer(serializers.ModelSerializer):
    """
    Visitation detail serializer
    """

    diagnoses = DiagnosisSerializer(many=True, read_only=True)
    vitals = VitalsSerializer(many=True, read_only=True)
    prescriptions = PrescriptionSerializer(many=True, read_only=True)
    allergies = AllergySerializer(many=True, read_only=True)
    notes = NotesSerializer(many=True, read_only=True)
    medical_history = MedicalHistorySerializer(many=True, read_only=True)
    # issued_by = UserSerializer(read_only=True)

    class Meta:
        model = Visitation
        fields = (
            "id",
            "patient",
            "title",
            "description",
            # diagnoses
            "diagnoses",
            # vitals
            "vitals",
            # prescriptions
            "prescriptions",
            # allergies
            "allergies",
            # notes
            "notes",
            # medical history
            "medical_history",
            # issued by
            "issued_by",
            "date_created",
            "last_updated",
        )
        read_only_fields = (
            "id",
            "date_created",
            "last_updated",
        )
