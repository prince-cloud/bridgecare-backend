from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from pharmacies.permissions import PharmacyProfileRequired
from .models import PharmacyProfile, Drug, StockMovement
from patients.models import Visitation, Prescription
from .serializers import (
    GetPrescriptionSerializer,
    PharmacyProfileSerializer,
    DrugInventorySerializer,
    DrugStockHistorySerializer,
)
from django.db.models import Q, Sum, Min
from django.utils import timezone


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
    filterset_fields = [
        "license_expiry_date",
        "district",
        "region",
        "delivery_available",
    ]
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


class InventoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for managing pharmacy inventory with search, pagination, and ordering
    """

    serializer_class = DrugInventorySerializer
    permission_classes = [PharmacyProfileRequired]
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

    def get_queryset(self):
        """Get inventory for the current pharmacy with annotations"""
        today = timezone.now().date()
        pharmacy = self.request.user.pharmacy_profile

        queryset = (
            Drug.objects.filter(pharmacy=pharmacy)
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
            .select_related("category")
        )
        return queryset

    @action(
        detail=True,
        methods=["get"],
        url_path="history",
        url_name="history",
    )
    def history(self, request, pk=None):
        """Confirm an appointment"""
        drug = self.get_object()

        history = StockMovement.objects.exclude(
            reason__in=[StockMovement.Reason.SALE],
        ).filter(drug=drug)

        return Response(
            data=DrugStockHistorySerializer(
                history, many=True, context={"request": request}
            ).data,
            status=status.HTTP_200_OK,
        )

    @action(
        detail=False,
        methods=["post"],
        url_path="get-prescription",
        url_name="get-prescription",
        permission_classes=[permissions.IsAuthenticated],
        serializer_class=GetPrescriptionSerializer,
    )
    def get_prescription(self, request):
        """
        Get prescription drugs and match with pharmacy inventory.
        Returns available and unavailable drugs separately.
        """
        serializer = GetPrescriptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        prescription_code = serializer.validated_data["prescription_code"]

        try:
            # Get visitation with that prescription code
            visitation = Visitation.objects.get(prescription_code=prescription_code)
        except Visitation.DoesNotExist:
            return Response(
                {"error": "Prescription not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Get prescriptions for that visitation
        prescriptions = Prescription.objects.filter(visitation=visitation)

        # Get available drugs in pharmacy inventory
        drug_queryset = self.get_queryset()

        # Separate available and unavailable drugs
        available_drugs = []
        unavailable_drugs = []

        for prescription in prescriptions:
            medication_name = (
                prescription.medication.strip().lower()
                if prescription.medication
                else ""
            )

            if not medication_name:
                continue

            # Try to find matching drug in inventory
            matched_drug = None

            # First, try exact match (case-insensitive)
            for drug in drug_queryset:
                if medication_name == drug.name.lower():
                    matched_drug = drug
                    break

            # If no exact match, try partial match (medication name in drug name)
            if not matched_drug:
                for drug in drug_queryset:
                    if (
                        medication_name in drug.name.lower()
                        or drug.name.lower() in medication_name
                    ):
                        matched_drug = drug
                        break

            if matched_drug:
                # Drug is available in inventory
                drug_data = DrugInventorySerializer(
                    matched_drug,
                    context={"request": request},
                ).data
                # Add prescription details to the drug data
                drug_data["prescription"] = {
                    "id": prescription.id,
                    "medication": prescription.medication,
                    "dosage": prescription.dosage,
                    "frequency": prescription.frequency,
                    "duration": prescription.duration,
                    "instructions": prescription.instructions,
                }
                available_drugs.append(drug_data)
            else:
                # Drug is not available in inventory
                unavailable_drugs.append(
                    {
                        "prescription": {
                            "id": prescription.id,
                            "medication": prescription.medication,
                            "dosage": prescription.dosage,
                            "frequency": prescription.frequency,
                            "duration": prescription.duration,
                            "instructions": prescription.instructions,
                        },
                        "available": False,
                        "message": f"{prescription.medication} is not available in this pharmacy",
                    }
                )

        return Response(
            {
                "prescription_code": prescription_code,
                "available_drugs": available_drugs,
                "unavailable_drugs": unavailable_drugs,
                "summary": {
                    "total_prescribed": len(prescriptions),
                    "available_count": len(available_drugs),
                    "unavailable_count": len(unavailable_drugs),
                },
            },
            status=status.HTTP_200_OK,
        )
