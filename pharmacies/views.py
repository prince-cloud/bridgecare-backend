from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .models import PharmacyProfile
from .serializers import PharmacyProfileSerializer


class PharmacyProfileViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing pharmacy profiles
    """

    queryset = PharmacyProfile.objects.all()
    serializer_class = PharmacyProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["pharmacy_type", "district", "region", "delivery_available"]
    search_fields = ["user__email", "pharmacy_name", "pharmacy_license", "district"]
    ordering_fields = ["pharmacy_name"]
    ordering = ["pharmacy_name"]

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]

    @action(
        detail=False, methods=["get"], permission_classes=[permissions.IsAuthenticated]
    )
    def nearby_pharmacies(self, request):
        """Get pharmacies near a location"""
        latitude = request.query_params.get("lat")
        longitude = request.query_params.get("lng")
        radius = request.query_params.get("radius", 10)  # km

        if not latitude or not longitude:
            return Response(
                {"error": "Latitude and longitude are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Simple distance calculation (in production, use PostGIS or similar)
        queryset = self.get_queryset().filter(
            latitude__isnull=False, longitude__isnull=False, user__is_active=True
        )

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def me(self, request):
        """Get current user's pharmacy profile"""
        try:
            profile = request.user.pharmacy_profile
            serializer = self.get_serializer(profile)
            return Response(serializer.data)
        except PharmacyProfile.DoesNotExist:
            return Response(
                {"error": "Pharmacy profile not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
