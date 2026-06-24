from rest_framework import viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend

from config.pagination import DefaultPagination
from .permissions import IsPlatformAdmin


class AdminModelViewSet(viewsets.ModelViewSet):
    """
    Base for every admin_api resource. Admin-only, paginated, with search,
    filter, and ordering wired up. Resource viewsets set queryset,
    serializer_class, search_fields, filterset_fields, ordering_fields.
    """

    permission_classes = [IsPlatformAdmin]
    pagination_class = DefaultPagination
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    ordering = ["-id"]


class AdminReadOnlyViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only variant for audit/log-style resources."""

    permission_classes = [IsPlatformAdmin]
    pagination_class = DefaultPagination
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    ordering = ["-id"]
