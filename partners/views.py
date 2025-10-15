from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .models import PartnerProfile
from .serializers import PartnerProfileSerializer


class PartnerProfileViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing partner profiles
    """
    queryset = PartnerProfile.objects.all()
    serializer_class = PartnerProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['organization_type', 'partnership_type', 'partnership_status', 'api_access_level']
    search_fields = ['user__email', 'organization_name', 'organization_type']

    def get_permissions(self):
        if self.action in ['list']:
            permission_classes = [permissions.IsAdminUser]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]

    @action(detail=False, methods=['get'])
    def me(self, request):
        """Get current user's partner profile"""
        try:
            profile = request.user.partner_profile
            serializer = self.get_serializer(profile)
            return Response(serializer.data)
        except PartnerProfile.DoesNotExist:
            return Response(
                {'error': 'Partner profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )
