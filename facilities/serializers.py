from rest_framework import serializers
from .models import (
    FacilityProfile,
    Locum,
    FacilityStaff,
    Ward,
    Bed,
    FacilityAppointment,
    LabTest,
    StaffInvitation,
)
from accounts.serializers import UserSerializer


class FacilityProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    occupied_beds_count = serializers.SerializerMethodField()
    total_beds_count = serializers.SerializerMethodField()
    staff_count = serializers.SerializerMethodField()

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
            "ghs_registration_number",
            "nhis_accreditation_number",
            "logo",
            "operating_hours",
            "latitude",
            "longitude",
            "slug",
            "is_active",
            "occupied_beds_count",
            "total_beds_count",
            "staff_count",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "slug", "created_at", "updated_at")

    def get_occupied_beds_count(self, obj):
        return Bed.objects.filter(ward__facility=obj, status=Bed.BedStatus.OCCUPIED).count()

    def get_total_beds_count(self, obj):
        return Bed.objects.filter(ward__facility=obj).count()

    def get_staff_count(self, obj):
        return obj.staff_members.filter(is_active=True).count()


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
        read_only_fields = ("id", "facility", "created_at", "updated_at")


class BedSerializer(serializers.ModelSerializer):
    patient_name = serializers.SerializerMethodField()
    patient_id_code = serializers.SerializerMethodField()

    class Meta:
        model = Bed
        fields = (
            "id",
            "ward",
            "bed_number",
            "status",
            "patient",
            "patient_name",
            "patient_id_code",
            "admitted_at",
            "notes",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def get_patient_name(self, obj):
        if obj.patient:
            parts = [obj.patient.first_name, obj.patient.last_name]
            return " ".join(p for p in parts if p) or None
        return None

    def get_patient_id_code(self, obj):
        return obj.patient.patient_id if obj.patient else None


class WardSerializer(serializers.ModelSerializer):
    beds = BedSerializer(many=True, read_only=True)
    occupied_beds = serializers.SerializerMethodField()
    available_beds = serializers.SerializerMethodField()
    total_beds = serializers.SerializerMethodField()

    class Meta:
        model = Ward
        fields = (
            "id",
            "facility",
            "name",
            "ward_type",
            "description",
            "capacity",
            "is_active",
            "beds",
            "occupied_beds",
            "available_beds",
            "total_beds",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "facility", "created_at", "updated_at")

    def get_occupied_beds(self, obj):
        return obj.beds.filter(status=Bed.BedStatus.OCCUPIED).count()

    def get_available_beds(self, obj):
        return obj.beds.filter(status=Bed.BedStatus.AVAILABLE).count()

    def get_total_beds(self, obj):
        return obj.beds.count()


class WardListSerializer(serializers.ModelSerializer):
    occupied_beds = serializers.SerializerMethodField()
    available_beds = serializers.SerializerMethodField()
    total_beds = serializers.SerializerMethodField()

    class Meta:
        model = Ward
        fields = (
            "id",
            "facility",
            "name",
            "ward_type",
            "description",
            "capacity",
            "is_active",
            "occupied_beds",
            "available_beds",
            "total_beds",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "facility", "created_at", "updated_at")

    def get_occupied_beds(self, obj):
        return obj.beds.filter(status=Bed.BedStatus.OCCUPIED).count()

    def get_available_beds(self, obj):
        return obj.beds.filter(status=Bed.BedStatus.AVAILABLE).count()

    def get_total_beds(self, obj):
        return obj.beds.count()


class FacilityAppointmentSerializer(serializers.ModelSerializer):
    patient_name = serializers.SerializerMethodField()
    patient_id_code = serializers.SerializerMethodField()
    provider_name = serializers.SerializerMethodField()

    class Meta:
        model = FacilityAppointment
        fields = (
            "id",
            "facility",
            "patient",
            "patient_name",
            "patient_id_code",
            "provider",
            "provider_name",
            "appointment_type",
            "consultation_type",
            "date",
            "start_time",
            "end_time",
            "reason",
            "notes",
            "status",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "facility", "created_at", "updated_at")

    def get_patient_name(self, obj):
        parts = [obj.patient.first_name, obj.patient.last_name]
        return " ".join(p for p in parts if p) or obj.patient.patient_id

    def get_patient_id_code(self, obj):
        return obj.patient.patient_id

    def get_provider_name(self, obj):
        return obj.provider.full_name if obj.provider else None


class LabTestSerializer(serializers.ModelSerializer):
    patient_name = serializers.SerializerMethodField()
    ordered_by_name = serializers.SerializerMethodField()

    class Meta:
        model = LabTest
        fields = (
            "id",
            "facility",
            "patient",
            "patient_name",
            "visitation",
            "ordered_by",
            "ordered_by_name",
            "test_name",
            "test_category",
            "status",
            "result",
            "result_file",
            "reference_range",
            "notes",
            "collected_at",
            "resulted_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "facility", "created_at", "updated_at")

    def get_patient_name(self, obj):
        parts = [obj.patient.first_name, obj.patient.last_name]
        return " ".join(p for p in parts if p) or obj.patient.patient_id

    def get_ordered_by_name(self, obj):
        return obj.ordered_by.full_name if obj.ordered_by else None


class StaffInvitationSerializer(serializers.ModelSerializer):
    class Meta:
        model = StaffInvitation
        fields = (
            "id",
            "facility",
            "email",
            "full_name",
            "profession",
            "position",
            "department",
            "status",
            "expires_at",
            "created_at",
        )
        read_only_fields = ("id", "facility", "status", "expires_at", "created_at")


class InviteStaffSerializer(serializers.Serializer):
    email = serializers.EmailField()
    full_name = serializers.CharField(max_length=200)
    profession = serializers.ChoiceField(choices=Locum.Profession.choices)
    position = serializers.CharField(max_length=100, required=False, allow_blank=True)
    department = serializers.CharField(max_length=100, required=False, allow_blank=True)


class RegisterPatientSerializer(serializers.Serializer):
    """Register a new walk-in patient and link to facility."""
    first_name = serializers.CharField(max_length=100)
    last_name = serializers.CharField(max_length=100)
    other_names = serializers.CharField(max_length=100, required=False, allow_blank=True)
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    gender = serializers.ChoiceField(choices=[("M", "Male"), ("F", "Female")], required=False, allow_blank=True)
    phone_number = serializers.CharField(max_length=20, required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True)
    blood_type = serializers.CharField(max_length=5, required=False, allow_blank=True)
    # Insurance
    insurance_provider = serializers.CharField(max_length=100, required=False, allow_blank=True)
    insurance_number = serializers.CharField(max_length=100, required=False, allow_blank=True)  # NHIS card number
    # Emergency
    emergency_contact_name = serializers.CharField(max_length=200, required=False, allow_blank=True)
    emergency_contact_phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    emergency_contact_relationship = serializers.CharField(max_length=100, required=False, allow_blank=True)
