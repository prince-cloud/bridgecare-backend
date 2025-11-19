from communities import models as community_models
from rest_framework.viewsets import ModelViewSet
from . import serializers
from rest_framework import filters
from django_filters.rest_framework import DjangoFilterBackend
from django_filters import rest_framework as django_filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status


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
