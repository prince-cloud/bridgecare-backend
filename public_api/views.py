from django.db.models import Q, Min, Sum
from communities import models as community_models
from rest_framework.viewsets import ModelViewSet
from django.utils import timezone
from professionals.models import ProfessionalProfile
from . import serializers
from rest_framework import filters
from django_filters.rest_framework import DjangoFilterBackend
from django_filters import rest_framework as django_filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from pharmacies import models as pharmacy_models


""" LOCUM JOBS """


class LocumJobFilter(django_filters.FilterSet):
    """
    Custom filter set for LocumJob that supports multiple role and renumeration_frequency filtering
    """

    role = django_filters.ModelMultipleChoiceFilter(
        queryset=community_models.LocumJobRole.objects.all(),
        field_name="role",
    )
    renumeration_frequency = django_filters.MultipleChoiceFilter(
        choices=[
            ("hourly", "Hourly"),
            ("daily", "Daily"),
            ("weekly", "Weekly"),
            ("monthly", "Monthly"),
            ("yearly", "Yearly"),
        ],
        field_name="renumeration_frequency",
    )

    class Meta:
        model = community_models.LocumJob
        fields = [
            "role",
            "organization",
            "is_active",
            "approved",
            "renumeration_frequency",
        ]


class LocumJobsViewset(ModelViewSet):
    queryset = community_models.LocumJob.objects.filter(approved=True, is_active=True)
    serializer_class = serializers.LocumJobSerializer
    http_method_names = ["get"]
    lookup_field = "slug"
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_class = LocumJobFilter
    search_fields = [
        "title",
        "description",
        "location",
        "organization__organization_name",
    ]
    ordering_fields = ["date_created", "renumeration", "title"]
    ordering = ["-date_created"]

    @action(
        detail=False,
        methods=["get"],
        url_path="roles",
        url_name="roles",
    )
    def get_roles(self, request):
        """Get recent locum jobs"""
        recent_jobs = community_models.LocumJobRole.objects.all()
        return Response(
            data=serializers.LocumJobRoleSerializer(
                recent_jobs,
                many=True,
                context={"request": request},
            ).data,
            status=status.HTTP_200_OK,
        )


""" HEATH PROFESSIONALS """


class ProfessionalProfileViewSet(ModelViewSet):
    """
    ViewSet for managing professional profiles
    """

    queryset = ProfessionalProfile.objects.filter(
        Q(availability__patient_visit_availability=True)
        | Q(availability__provider_visit_availability=True)
        | Q(availability__telehealth_availability=True),
        is_verified=True,
    )
    serializer_class = serializers.ProfessionalProfileSerializer
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = [
        "profession",
        "specialization",
        "education_status",
        "facility_affiliation",
        "is_verified",
    ]
    http_method_names = ["get"]


""" PHARMACIES """


class InventoryViewSet(ModelViewSet):
    """
    Public pharmacy inventory. Supports location-based sorting via ?lat=&lng= query params.
    """

    serializer_class = serializers.DrugInventorySerializer
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    search_fields = ["name", "category__name", "base_unit"]
    ordering_fields = [
        "name",
        "available_quantity",
        "nearest_expiry",
        "unit_price",
        "created_at",
    ]
    ordering = ["name"]
    http_method_names = ["get"]

    def get_queryset(self):
        today = timezone.now().date()
        return (
            pharmacy_models.Drug.objects.filter(pharmacy__is_verified=True)
            .annotate(
                available_quantity=Sum(
                    "movements__quantity",
                    filter=Q(movements__batch__expiry_date__gte=today),
                ),
                nearest_expiry=Min(
                    "batches__expiry_date",
                    filter=Q(batches__expiry_date__gte=today),
                ),
            )
            .filter(available_quantity__gt=0)
            .select_related("category", "pharmacy")
        )

    def list(self, request, *args, **kwargs):
        from .serializers import haversine_km

        lat_param = request.query_params.get("lat")
        lng_param = request.query_params.get("lng")

        queryset = self.filter_queryset(self.get_queryset())

        # Location-aware path: sort by distance
        if lat_param and lng_param:
            try:
                user_lat = float(lat_param)
                user_lng = float(lng_param)
            except (ValueError, TypeError):
                user_lat = user_lng = None
        else:
            user_lat = user_lng = None

        if user_lat is not None:
            drugs = list(queryset)
            distances = {}
            for drug in drugs:
                p = drug.pharmacy
                if p.latitude and p.longitude:
                    distances[drug.id] = haversine_km(
                        user_lat, user_lng, float(p.latitude), float(p.longitude)
                    )
                else:
                    distances[drug.id] = float("inf")

            drugs.sort(key=lambda d: distances[d.id])

            page = self.paginate_queryset(drugs)
            ctx = {**self.get_serializer_context(), "distances": distances}
            if page is not None:
                serializer = self.get_serializer(page, many=True, context=ctx)
                return self.get_paginated_response(serializer.data)
            serializer = self.get_serializer(drugs, many=True, context=ctx)
            return Response(serializer.data)

        # Default path (no location)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class HealthProgramViewSet(ModelViewSet):
    """
    ViewSet for managing health programs
    """

    queryset = community_models.HealthProgram.objects.filter(
        status__in=["approved", "in_progress"]
    )
    serializer_class = serializers.HealthProgramSerializer
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = [
        "program_type",
        "status",
        "district",
        "region",
        "organization",
        "created_by",
    ]
    search_fields = [
        "program_name",
        "description",
        "location_name",
        "organization__organization_name",
    ]
    ordering_fields = ["start_date", "created_at", "actual_participants"]
    ordering = ["-start_date"]
    http_method_names = ["get"]
