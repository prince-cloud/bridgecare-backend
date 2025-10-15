from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .models import ProfessionalProfile
from .serializers import ProfessionalProfileSerializer


class ProfessionalProfileViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing professional profiles
    """
    queryset = ProfessionalProfile.objects.all()
    serializer_class = ProfessionalProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['practice_type', 'years_of_experience', 'license_issuing_body']
    search_fields = ['user__email', 'license_number', 'practice_type']
    ordering_fields = ['years_of_experience', 'hourly_rate']
    ordering = ['-years_of_experience']

    def get_permissions(self):
        if self.action in ['list']:
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]

    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def available_locums(self, request):
        """Get available locum professionals"""
        queryset = self.get_queryset().filter(
            availability_schedule__isnull=False,
            user__is_active=True
        )
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def me(self, request):
        """Get current user's professional profile"""
        try:
            profile = request.user.professional_profile
            serializer = self.get_serializer(profile)
            return Response(serializer.data)
        except ProfessionalProfile.DoesNotExist:
            return Response(
                {'error': 'Professional profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )
