from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .models import ProfessionalProfile
from .serializers import ProfessionalProfileSerializer
from .models import Profession, Specialization, LicenceIssueAuthority
from .serializers import (
    ProfessionsSerializer,
    SpecializationSerializer,
    LicenceIssueAuthoritySerializer,
)


class ProfessionsViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing professions
    """

    queryset = Profession.objects.filter(is_active=True)
    serializer_class = ProfessionsSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post"]


class SpecializationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing specializations
    """

    queryset = Specialization.objects.filter(is_active=True)
    serializer_class = SpecializationSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post"]


class LicenceIssueAuthorityViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing licence issue authorities
    """

    queryset = LicenceIssueAuthority.objects.filter(is_active=True)
    serializer_class = LicenceIssueAuthoritySerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post"]


class ProfessionalProfileViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing professional profiles
    """

    queryset = ProfessionalProfile.objects.all()
    serializer_class = ProfessionalProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
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
        "is_active",
    ]
    http_method_names = ["get", "post", "put", "patch"]
