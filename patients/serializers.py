import json
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
from django.utils import timezone


class PatientProfileSerializer(serializers.ModelSerializer):
    """
    Patient profile serializer
    """

    # user = UserSerializer(read_only=True)
    current_visitation = serializers.SerializerMethodField(read_only=True)

    def get_current_visitation(self, obj):
        visitation = Visitation.objects.filter(
            patient=obj, status=Visitation.VisitationStatus.OPENED
        ).first()
        if visitation:
            return visitation.id
        return None

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
            "current_visitation",
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


class PatientChatDetailSerializer(serializers.ModelSerializer):
    """
    Patient profile serializer for chat detail
    """

    class Meta:
        model = PatientProfile
        fields = (
            "id",
            "patient_id",
            "first_name",
            "surname",
            "last_name",
            "gender",
            "profile_picture",
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
            "status",
            "date_created",
            "last_updated",
        )
        read_only_fields = (
            "id",
            "date_created",
            "last_updated",
            "status",
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

    custom_vitals = serializers.SerializerMethodField(read_only=True)

    def get_custom_vitals(self, obj):
        if obj.custom_vitals is not None:
            return json.loads(obj.custom_vitals)
        return None

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

    diagnoses = DiagnosisSerializer(many=False, read_only=True)
    vitals = VitalsSerializer(many=False, read_only=True)
    prescriptions = PrescriptionSerializer(many=True, read_only=True)
    allergies = serializers.SerializerMethodField(read_only=True)
    notes = NotesSerializer(many=True, read_only=True)
    medical_history = serializers.SerializerMethodField(read_only=True)
    # issued_by = UserSerializer(read_only=True)

    def get_medical_history(self, obj):
        patient = obj.patient
        history = MedicalHistory.objects.filter(patient=patient).all()
        return MedicalHistorySerializer(history, many=True).data

    def get_allergies(self, obj):
        patient = obj.patient
        allergies = Allergy.objects.filter(patient=patient).all()
        return AllergySerializer(allergies, many=True).data

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


class PatientVitalDetailSerializer(serializers.ModelSerializer):
    """
    Visitation detail serializer
    """

    diagnoses = serializers.SerializerMethodField(read_only=True)
    vitals = serializers.SerializerMethodField(read_only=True)
    prescriptions = serializers.SerializerMethodField(read_only=True)
    allergies = serializers.SerializerMethodField(read_only=True)
    notes = serializers.SerializerMethodField(read_only=True)
    medical_history = serializers.SerializerMethodField(read_only=True)
    # issued_by = UserSerializer(read_only=True)

    def get_diagnoses(self, obj):
        diagnoses = Diagnosis.objects.filter(visitation=obj).all()[:5]
        return DiagnosisSerializer(diagnoses, many=True).data

    def get_vitals(self, obj):
        vitals = Vitals.objects.filter(visitation=obj).all()[:5]
        return VitalsSerializer(vitals, many=True).data

    def get_prescriptions(self, obj):
        prescriptions = Prescription.objects.filter(visitation=obj).all()[:5]
        return PrescriptionSerializer(prescriptions, many=True).data

    def get_notes(self, obj):
        notes = Notes.objects.filter(visitation=obj).all()[:5]
        return NotesSerializer(notes, many=True).data

    def get_medical_history(self, obj):
        patient = obj.patient
        history = MedicalHistory.objects.filter(patient=patient).all()[:5]
        return MedicalHistorySerializer(history, many=True).data

    def get_allergies(self, obj):
        patient = obj.patient
        allergies = Allergy.objects.filter(patient=patient).all()[:5]
        return AllergySerializer(allergies, many=True).data

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


class PatientSearchWithIdSerializer(serializers.ModelSerializer):
    """
    Patient search with id serializer
    """

    class Meta:
        model = PatientProfile
        fields = (
            "id",
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "patient_id",
        )
        read_only_fields = ("id",)
