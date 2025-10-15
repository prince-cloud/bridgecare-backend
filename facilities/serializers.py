from rest_framework import serializers
from .models import Facility, FacilityProfile
from accounts.serializers import UserSerializer


class FacilitySerializer(serializers.ModelSerializer):
    """
    Facility serializer
    """
    staff_count = serializers.SerializerMethodField()

    class Meta:
        model = Facility
        fields = (
            "id",
            "name",
            "facility_code",
            "facility_type",
            "address",
            "district",
            "region",
            "phone_number",
            "email",
            "latitude",
            "longitude",
            "is_active",
            "staff_count",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def get_staff_count(self, obj):
        return obj.staff.count()


class FacilityProfileSerializer(serializers.ModelSerializer):
    """
    Facility profile serializer
    """
    user = UserSerializer(read_only=True)
    facility_name = serializers.CharField(source="facility.name", read_only=True)
    supervisor_name = serializers.SerializerMethodField()

    class Meta:
        model = FacilityProfile
        fields = (
            "id",
            "user",
            "facility",
            "facility_name",
            "employee_id",
            "department",
            "position",
            "employment_type",
            "hire_date",
            "shift_schedule",
            "working_hours",
            "can_prescribe",
            "can_access_patient_data",
            "can_manage_inventory",
            "can_schedule_appointments",
            "supervisor",
            "supervisor_name",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def get_supervisor_name(self, obj):
        if obj.supervisor:
            return f"{obj.supervisor.first_name} {obj.supervisor.last_name}"
        return None

