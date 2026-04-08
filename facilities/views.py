from dj_rest_auth.views import APIView
from django.db.models import Q
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from helpers import exceptions
from patients.models import PatientProfile
from patients.serializers import PatientProfileListSerializer
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


class PatientView(APIView):
    """View for patients"""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = PatientProfileListSerializer

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="search",
                type={"type": "string"},
                location=OpenApiParameter.QUERY,
                required=False,
                description="Search term to filter patients",
            ),
            OpenApiParameter(
                name="search_type",
                type={"type": "string"},
                location=OpenApiParameter.QUERY,
                required=False,
                enum=["patient_id", "general"],
                description="Type of search: 'patient_id' for exact match on patient ID, 'general' for partial match on first_name, last_name, email, or phone_number (searches both PatientProfile and User model fields)",
            ),
        ],
        responses={200: PatientProfileListSerializer(many=True)},
    )
    def get(self, request):
        """
        Get all patients. Optionally filter by search query parameter.
        - If search_type is 'patient_id', performs exact match on patient_id
        - If search_type is 'general' or not provided, performs partial match (icontains) on first_name, last_name, email, and phone_number from both PatientProfile and User model
        """
        user = request.user
        if not (hasattr(user, "facility_profile") or hasattr(user, "facility_staff")):
            print("==== user has no facility profile or facility staff")
            raise exceptions.GeneralException(
                "You are not authorized to access this resource."
            )

        facility_profile = user.facility_profile or user.facility_staff.facility

        # Get patient IDs from PatientAccess objects
        patient_ids = facility_profile.patient_access.filter(
            is_active=True
        ).values_list("patient_id", flat=True)

        # Get the actual PatientProfile objects
        patient_profiles = PatientProfile.objects.filter(id__in=patient_ids)

        # Get search parameters
        search_query = request.query_params.get("search")
        search_type = request.query_params.get("search_type", "general")

        # Apply search filters if search query is provided
        if search_query:
            search_query = search_query.strip()

            if search_type == "patient_id":
                # Exact match on patient_id
                patient_profiles = patient_profiles.filter(patient_id=search_query)
                if not patient_profiles.exists():
                    raise exceptions.GeneralException(
                        f"Patient with ID '{search_query}' not found or you don't have access to this patient."
                    )
            else:
                # General search with icontains on first_name, last_name, email, and phone_number
                # Searches both PatientProfile fields and related User model fields
                search_filter = (
                    Q(first_name__icontains=search_query)
                    | Q(last_name__icontains=search_query)
                    | Q(email__icontains=search_query)
                    | Q(phone_number__icontains=search_query)
                    | Q(user__first_name__icontains=search_query)
                    | Q(user__last_name__icontains=search_query)
                    | Q(user__email__icontains=search_query)
                    | Q(user__phone_number__icontains=search_query)
                )
                patient_profiles = patient_profiles.filter(search_filter)

                if not patient_profiles.exists():
                    raise exceptions.GeneralException(
                        f"No patients found matching '{search_query}'"
                    )

        # Paginate the results
        paginator = PageNumberPagination()
        paginator.page_size = 64  # Match default page size from settings
        paginated_queryset = paginator.paginate_queryset(patient_profiles, request)

        serializer = self.serializer_class(paginated_queryset, many=True)
        return paginator.get_paginated_response(serializer.data)
