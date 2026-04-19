from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from .models import PartnerProfile, Subsidy, ProgramPartnershipRequest, ProgramMonitor
from accounts.serializers import UserSerializer
from communities.serializers import (
    HealthProgramSerializer,
    InterventionResponseSerializer,
    ProgramInterventionSerializer,
)


def _coerce_text_choice(choice_type, raw):
    """Map API / UI input to a canonical TextChoices value, or None if unknown."""
    if raw in (None, ""):
        return None
    if isinstance(raw, choice_type):
        return raw.value
    s = str(raw).strip()
    if s in choice_type.values:
        return s
    s_lower = s.lower()
    for val, label in choice_type.choices:
        if s_lower == val.lower():
            return val
        if s_lower == str(label).lower():
            return val
        slugish = str(label).lower().replace(" ", "_").replace("-", "_")
        if s_lower == slugish:
            return val
    return None


class LenientChoiceField(serializers.CharField):
    """Accepts TextChoices value, case-insensitive value, or human-readable label."""

    def __init__(self, choice_type, **kwargs):
        self.choice_type = choice_type
        super().__init__(**kwargs)

    def to_internal_value(self, data):
        normalized = _coerce_text_choice(self.choice_type, data)
        if normalized is None:
            allowed = ", ".join(self.choice_type.values)
            raise ValidationError(f'"{data}" is not a valid choice. Expected one of: {allowed}.')
        return super().to_internal_value(normalized)


_SUBSIDY_INPUT_ALIASES = {
    "totalBudget": "total_budget",
    "budgetUsed": "budget_used",
    "subsidyType": "subsidy_type",
    "startDate": "start_date",
    "endDate": "end_date",
}


class PartnerProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    active_subsidies_count = serializers.SerializerMethodField()
    monitored_programs_count = serializers.SerializerMethodField()

    class Meta:
        model = PartnerProfile
        fields = (
            "id", "user", "slug",
            "organization_name", "organization_type", "organization_size",
            "registration_number", "logo",
            "organization_phone", "organization_email", "organization_address",
            "region", "district", "website",
            "partnership_type", "partnership_status",
            "partnership_start_date", "partnership_end_date",
            "is_verified",
            "can_access_analytics", "can_manage_subsidies", "can_view_patient_data",
            "contact_person_name", "contact_person_title", "contact_person_phone",
            "active_subsidies_count", "monitored_programs_count",
            "created_at", "updated_at",
        )
        read_only_fields = ("id", "slug", "is_verified", "can_access_analytics",
                            "can_manage_subsidies", "can_view_patient_data", "created_at", "updated_at")

    def get_active_subsidies_count(self, obj):
        return obj.subsidies.filter(status="active").count()

    def get_monitored_programs_count(self, obj):
        return obj.program_monitors.filter(is_active=True).count()


class SubsidySerializer(serializers.ModelSerializer):
    budget_remaining = serializers.ReadOnlyField()
    utilization_pct = serializers.ReadOnlyField()
    subsidy_type = LenientChoiceField(Subsidy.SubsidyType, required=False)
    status = LenientChoiceField(Subsidy.Status, required=False, max_length=20)

    class Meta:
        model = Subsidy
        fields = (
            "id", "partner",
            "name", "subsidy_type",
            "total_budget", "budget_used", "budget_remaining", "utilization_pct",
            "target", "start_date", "end_date",
            "status", "notes",
            "created_at", "updated_at",
        )
        read_only_fields = ("id", "partner", "budget_remaining", "utilization_pct", "created_at", "updated_at")

    def to_internal_value(self, data):
        if isinstance(data, dict):
            data = {_SUBSIDY_INPUT_ALIASES.get(k, k): v for k, v in data.items()}
        return super().to_internal_value(data)


class ProgramSummarySerializer(serializers.Serializer):
    """Lightweight program representation for nested use."""
    id = serializers.UUIDField()
    program_name = serializers.CharField()
    description = serializers.CharField()
    region = serializers.CharField()
    district = serializers.CharField()
    start_date = serializers.DateField()
    end_date = serializers.DateField(allow_null=True)
    status = serializers.CharField()
    target_participants = serializers.IntegerField()
    actual_participants = serializers.IntegerField()
    title_image = serializers.SerializerMethodField()
    organization_name = serializers.SerializerMethodField()
    organization_id = serializers.SerializerMethodField()

    def get_title_image(self, obj):
        request = self.context.get("request")
        if obj.title_image:
            url = obj.title_image.url
            return request.build_absolute_uri(url) if request else url
        return None

    def get_organization_name(self, obj):
        return obj.organization.organization_name if obj.organization else None

    def get_organization_id(self, obj):
        return str(obj.organization.id) if obj.organization else None


class ProgramPartnershipRequestSerializer(serializers.ModelSerializer):
    partner_name = serializers.CharField(source="partner.organization_name", read_only=True)
    partner_type = serializers.CharField(source="partner.organization_type", read_only=True)
    partner_logo = serializers.ImageField(source="partner.logo", read_only=True)
    program_name = serializers.CharField(source="program.program_name", read_only=True)
    program_region = serializers.CharField(source="program.region", read_only=True)
    reviewed_by_email = serializers.CharField(source="reviewed_by.email", read_only=True, allow_null=True)

    class Meta:
        model = ProgramPartnershipRequest
        fields = (
            "id", "partner", "partner_name", "partner_type", "partner_logo",
            "program", "program_name", "program_region",
            "direction", "status",
            "message", "report_frequency", "contact", "notes",
            "reviewed_by", "reviewed_by_email", "reviewed_at", "review_note",
            "created_at", "updated_at",
        )
        read_only_fields = ("id", "partner", "direction", "status", "reviewed_by",
                            "reviewed_at", "review_note", "created_at", "updated_at")


class ProgramMonitorSerializer(serializers.ModelSerializer):
    partner_name = serializers.CharField(source="partner.organization_name", read_only=True)
    program_name = serializers.CharField(source="program.program_name", read_only=True)
    program_region = serializers.CharField(source="program.region", read_only=True)
    program_status = serializers.CharField(source="program.status", read_only=True)
    program_start_date = serializers.DateField(source="program.start_date", read_only=True)
    program_end_date = serializers.DateField(source="program.end_date", read_only=True, allow_null=True)
    actual_participants = serializers.IntegerField(source="program.actual_participants", read_only=True)
    target_participants = serializers.IntegerField(source="program.target_participants", read_only=True)
    organization_name = serializers.CharField(source="program.organization.organization_name", read_only=True)

    class Meta:
        model = ProgramMonitor
        fields = (
            "id", "partner", "partner_name",
            "program", "program_name", "program_region", "program_status",
            "program_start_date", "program_end_date",
            "actual_participants", "target_participants",
            "organization_name",
            "report_frequency", "contact", "is_active",
            "created_at",
        )
        read_only_fields = ("id", "partner", "program", "created_at")


class ProgramMonitorDetailSerializer(ProgramMonitorSerializer):
    program_detail = HealthProgramSerializer(source="program", read_only=True)

    class Meta(ProgramMonitorSerializer.Meta):
        fields = ProgramMonitorSerializer.Meta.fields + ("program_detail",)


class PartnerProgramInterventionSerializer(ProgramInterventionSerializer):
    class Meta(ProgramInterventionSerializer.Meta):
        fields = ProgramInterventionSerializer.Meta.fields


class PartnerInterventionResponseSerializer(InterventionResponseSerializer):
    class Meta(InterventionResponseSerializer.Meta):
        fields = InterventionResponseSerializer.Meta.fields


class PartnerDiscoverSerializer(serializers.ModelSerializer):
    """Lightweight partner profile for organisations browsing available partners."""
    logo = serializers.ImageField(read_only=True)

    class Meta:
        model = PartnerProfile
        fields = (
            "id", "organization_name", "organization_type", "organization_size",
            "partnership_type", "region", "district",
            "organization_email", "organization_phone", "website",
            "contact_person_name", "contact_person_title",
            "logo", "is_verified",
        )
