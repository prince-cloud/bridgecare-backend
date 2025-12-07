from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .models import (
    Allergy,
    Diagnosis,
    MedicalHistory,
    Notes,
    PatientProfile,
    Prescription,
    Visitation,
    Vitals,
)
from .serializers import (
    AllergySerializer,
    DiagnosisSerializer,
    MedicalHistorySerializer,
    NotesSerializer,
    PatientProfileSerializer,
    PrescriptionSerializer,
    VisitationDetailSerializer,
    VisitationSerializer,
    VitalsSerializer,
)
from .permissions import HealthProfessionalRequired


class PatientProfileViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing patient profiles
    """

    queryset = PatientProfile.objects.all()
    serializer_class = PatientProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["blood_type"]
    search_fields = ["user__email", "emergency_contact_name", "insurance_provider"]

    def get_permissions(self):
        if self.action in ["list"]:
            permission_classes = [permissions.IsAdminUser]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]

    @action(
        detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated]
    )
    def update_health_info(self, request, pk=None):
        """Update patient health information"""
        patient = self.get_object()

        # Check if user can access this patient's data
        if not (request.user.is_staff or patient.user == request.user):
            return Response(
                {"error": "Permission denied"}, status=status.HTTP_403_FORBIDDEN
            )

        serializer = self.get_serializer(patient, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["get"])
    def me(self, request):
        """Get current user's patient profile"""
        try:
            profile = request.user.patient_profile
            serializer = self.get_serializer(profile)
            return Response(serializer.data)
        except PatientProfile.DoesNotExist:
            return Response(
                {"error": "Patient profile not found"}, status=status.HTTP_404_NOT_FOUND
            )

    @action(
        detail=True,
        methods=["get"],
        permission_classes=[permissions.IsAuthenticated],
        url_path="medical-records",
        url_name="medical-records",
    )
    def medical_records(self, request, pk=None):
        """Get patient vitals"""
        patient = self.get_object()

        # medical history
        diagnoses = Diagnosis.objects.filter(visitation__patient=patient).all()[:5]
        diagnoses_data = DiagnosisSerializer(diagnoses, many=True).data

        vitals = Vitals.objects.filter(visitation__patient=patient).all()[:5]
        vital_data = VitalsSerializer(vitals, many=True).data

        prescriptions = Prescription.objects.filter(visitation__patient=patient).all()[
            :5
        ]
        prescription_data = PrescriptionSerializer(prescriptions, many=True).data

        notes = Notes.objects.filter(visitation__patient=patient).all()[:5]
        notes_data = NotesSerializer(notes, many=True).data

        history = MedicalHistory.objects.filter(patient=patient).all()[:5]
        history_data = MedicalHistorySerializer(history, many=True).data

        allergies = Allergy.objects.filter(patient=patient).all()[:5]
        allergies_data = AllergySerializer(allergies, many=True).data

        # timeline data
        timeline_data = [
            {
                "title": visitation.title,
                "date": visitation.date_created,
            }
            for visitation in Visitation.objects.filter(patient=patient).all()[:5]
        ]

        data = {
            "diagnoses": diagnoses_data,
            "vitals": vital_data,
            "prescriptions": prescription_data,
            "notes": notes_data,
            "history": history_data,
            "allergies": allergies_data,
            "timeline": timeline_data,
        }
        return Response(data=data, status=status.HTTP_200_OK)


class VisitationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing visits
    """

    queryset = Visitation.objects.all()
    serializer_class = VisitationSerializer
    permission_classes = [HealthProfessionalRequired]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["title", "description"]
    search_fields = ["title", "description"]
    http_method_names = ["get", "post"]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return VisitationDetailSerializer
        return VisitationSerializer

    def perform_create(self, serializer):
        professional = self.request.user.professional_profile
        return serializer.save(issued_by=professional)


class DiagnosisViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing diagnoses
    """

    queryset = Diagnosis.objects.all()
    serializer_class = DiagnosisSerializer
    permission_classes = [HealthProfessionalRequired]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["diagnosis"]
    search_fields = ["diagnosis"]
    http_method_names = ["get", "post", "patch"]


class VitalsViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing vitals
    """

    queryset = Vitals.objects.all()
    serializer_class = VitalsSerializer
    permission_classes = [HealthProfessionalRequired]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    http_method_names = ["get", "post", "patch"]


class PrescriptionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing prescriptions
    """

    queryset = Prescription.objects.all()
    serializer_class = PrescriptionSerializer
    permission_classes = [HealthProfessionalRequired]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]

    http_method_names = ["get", "post", "patch"]


class AllergyViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing allergies
    """

    queryset = Allergy.objects.all()
    serializer_class = AllergySerializer
    permission_classes = [HealthProfessionalRequired]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]

    http_method_names = ["get", "post", "patch"]


class NotesViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing notes
    """

    queryset = Notes.objects.all()
    serializer_class = NotesSerializer
    permission_classes = [HealthProfessionalRequired]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    http_method_names = ["get", "post", "patch"]

    def perform_create(self, serializer):
        professional = self.request.user.professional_profile
        return serializer.save(issued_by=professional)


class MedicalHistoryViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing medical history
    """

    queryset = MedicalHistory.objects.all()
    serializer_class = MedicalHistorySerializer
    permission_classes = [HealthProfessionalRequired]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    http_method_names = ["get", "post", "patch"]
