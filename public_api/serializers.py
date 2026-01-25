from rest_framework import serializers
from accounts.serializers import UserSerializer
from communities import models as community_models
from professionals.models import Profession, ProfessionalProfile, Specialization
from pharmacies.models import PharmacyProfile, Drug, DrugCategory
from django.utils import timezone


class LocumJobRoleSerializer(serializers.ModelSerializer):
    """
    Serializer for locum job roles
    """

    class Meta:
        model = community_models.LocumJobRole
        fields = (
            "id",
            "name",
        )


class LocumJobSerializer(serializers.ModelSerializer):
    """
    Serializer for locum jobs
    """

    role_name = serializers.CharField(source="role.name", read_only=True)
    organization_name = serializers.CharField(
        source="organization.organization_name", read_only=True
    )
    organization_type = serializers.CharField(
        source="organization.organization_type", read_only=True
    )
    renumeration_display = serializers.SerializerMethodField()

    class Meta:
        model = community_models.LocumJob
        fields = (
            "id",
            "role",
            "role_name",
            "title",
            "organization",
            "organization_name",
            "organization_type",
            "description",
            "requirements",
            "location",
            "title_image",
            "job_type",
            "renumeration",
            "renumeration_frequency",
            "renumeration_display",
            "slug",
            "date_created",
            "last_updated",
        )
        read_only_fields = ("id", "date_created", "last_updated")

    def get_renumeration_display(self, obj):
        """Format renumeration with frequency"""
        if obj.job_type == "volunteering":
            return "Volunteering"
        if obj.renumeration and obj.renumeration_frequency:
            return f"{obj.renumeration} per {obj.renumeration_frequency}"
        return None


class ProfessionsSerializer(serializers.ModelSerializer):
    """
    Professions serializer
    """

    class Meta:
        model = Profession
        fields = (
            "id",
            "name",
            "description",
        )


class SpecializationSerializer(serializers.ModelSerializer):

    class Meta:
        model = Specialization
        fields = (
            "id",
            "name",
            "description",
        )


class ProfessionalProfileSerializer(serializers.ModelSerializer):
    """
    Professional profile serializer
    """

    user = UserSerializer(read_only=True)
    profession = ProfessionsSerializer(read_only=True)
    specialization = SpecializationSerializer(read_only=True)

    availability = serializers.SerializerMethodField()

    def get_availability(self, obj):
        if hasattr(obj, "availability"):
            return {
                "patient_visit_availability": obj.availability.patient_visit_availability,
                "provider_visit_availability": obj.availability.provider_visit_availability,
                "telehealth_availability": obj.availability.telehealth_availability,
            }
        return {
            "patient_visit_availability": False,
            "provider_visit_availability": False,
            "telehealth_availability": False,
        }

    profile_completion_exceptions = serializers.SerializerMethodField()

    def get_profile_completion_exceptions(self, obj):
        data = []
        if not obj.education_status:
            data.append("Please update your educational status.")
        if obj.education_status and not obj.education_histories.exists():
            data.append("Please update your educational history.")
        if obj.education_status == "PRACTICING" and not (
            obj.profession or not obj.license_number
        ):
            data.append("Please update your profession and license number.")
        return data

    class Meta:
        model = ProfessionalProfile
        fields = (
            "id",
            "user",
            "education_status",
            "profession",
            "specialization",
            "availability",
            "facility_affiliation",
            "license_issuing_authority",
            "years_of_experience",
            "is_profile_completed",
            "profile_completion_exceptions",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class ShortPharmacyProfileSerializer(serializers.ModelSerializer):
    """
    Pharmacy profile serializer
    """

    class Meta:
        model = PharmacyProfile
        fields = (
            "id",
            "pharmacy_name",
            "address",
            "district",
            "region",
            "latitude",
            "longitude",
            "phone_number",
            "email",
            "delivery_available",
            "delivery_radius",
        )
        read_only_fields = ("id",)


class DrugCategorySerializer(serializers.ModelSerializer):
    """
    Drug category serializer
    """

    class Meta:
        model = DrugCategory
        fields = ("id", "name")
        read_only_fields = ("id",)


class DrugInventorySerializer(serializers.ModelSerializer):
    available_quantity = serializers.IntegerField(read_only=True)
    nearest_expiry = serializers.DateField(read_only=True)

    is_expired = serializers.SerializerMethodField()
    low_quantity = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    category = DrugCategorySerializer(read_only=True)

    pharmacy = ShortPharmacyProfileSerializer(read_only=True)

    class Meta:
        model = Drug
        fields = [
            "id",
            "image",
            "name",
            "base_unit",
            "unit_price",
            "available_quantity",
            "nearest_expiry",
            "is_expired",
            "low_quantity",
            "status",
            "category",
            "pharmacy",
        ]

    def get_is_expired(self, obj):
        if not obj.nearest_expiry:
            return False
        return obj.nearest_expiry < timezone.now().date()

    def get_low_quantity(self, obj):
        return (obj.available_quantity or 0) <= obj.low_stock_threshold

    def get_status(self, obj):
        qty = obj.available_quantity or 0
        threshold = obj.low_stock_threshold

        if qty <= 0:
            return "OUT OF STOCK"
        elif qty <= threshold:
            return "LOW STOCK"
        return "IN STOCK"
