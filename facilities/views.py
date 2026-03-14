from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .models import FacilityProfile, Locum, FacilityStaff
from .serializers import (
    FacilityProfileSerializer,
    LocumSerializer,
    FacilityStaffSerializer,
)


class FacilityProfileViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing facility profiles
    """

    queryset = FacilityProfile.objects.all()
    serializer_class = FacilityProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["facility_type", "region", "district", "is_active"]
    search_fields = ["name", "address", "district", "region"]

    def get_permissions(self):
        if self.action in ["list"]:
            permission_classes = [permissions.IsAdminUser]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]

    @action(detail=False, methods=["get"])
    def me(self, request):
        """Get current user's facility profile"""
        try:
            profile = request.user.facility_profile
            serializer = self.get_serializer(profile)
            return Response(serializer.data)
        except FacilityProfile.DoesNotExist:
            return Response(
                {"error": "Facility profile not found"},
                status=status.HTTP_404_NOT_FOUND,
            )


class LocumViewSet(viewsets.ModelViewSet):
    queryset = Locum.objects.all()
    serializer_class = LocumSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["profession", "is_available", "region", "district"]
    search_fields = ["full_name", "email", "license_number"]
    ordering_fields = ["created_at", "years_of_experience", "full_name"]
    ordering = ["-created_at"]


class StaffViewSet(viewsets.ModelViewSet):
    queryset = FacilityStaff.objects.all()
    serializer_class = FacilityStaffSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["facility", "profession", "department", "is_active"]
    search_fields = ["full_name", "employee_id", "position", "facility__name", "email"]
    ordering_fields = ["created_at", "hire_date", "full_name"]
    ordering = ["-created_at"]

    def get_queryset(self):
        queryset = super().get_queryset().select_related("facility", "user")
        user = self.request.user
        if user.is_staff:
            return queryset
        if hasattr(user, "facility_profile"):
            return queryset.filter(facility=user.facility_profile)
        return queryset.none()

    def perform_create(self, serializer):
        user = self.request.user
        facility = serializer.validated_data.get("facility")
        if hasattr(user, "facility_profile"):
            facility = user.facility_profile
        serializer.save(facility=facility)
