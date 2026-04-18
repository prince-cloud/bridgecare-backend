import secrets
from datetime import timedelta

from dj_rest_auth.views import APIView
from django.db.models import Q, Count
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from accounts.tasks import generic_send_mail
from helpers import exceptions
from patients.models import PatientProfile, FacilityPatientAccess
from patients.serializers import PatientProfileListSerializer, PatientProfileSerializer
from .models import (
    FacilityProfile,
    Locum,
    FacilityStaff,
    Ward,
    Bed,
    FacilityAppointment,
    LabTest,
    StaffInvitation,
)
from .serializers import (
    FacilityProfileSerializer,
    LocumSerializer,
    FacilityStaffSerializer,
    WardSerializer,
    BedSerializer,
    FacilityAppointmentSerializer,
    LabTestSerializer,
    StaffInvitationSerializer,
    InviteStaffSerializer,
    RegisterPatientSerializer,
)


def get_facility_for_user(user):
    """Return the facility for a logged-in user — either as admin or staff."""
    if hasattr(user, "facility_profile"):
        return user.facility_profile
    if hasattr(user, "facility_staff") and user.facility_staff:
        return user.facility_staff.facility
    return None


class IsFacilityUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and get_facility_for_user(request.user) is not None


class FacilityProfileViewSet(viewsets.ModelViewSet):
    queryset = FacilityProfile.objects.all()
    serializer_class = FacilityProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["facility_type", "region", "district", "is_active"]
    search_fields = ["name", "address", "district", "region"]

    def get_permissions(self):
        if self.action in ["list"]:
            return [permissions.IsAdminUser()]
        return [permissions.IsAuthenticated()]

    @action(detail=False, methods=["get", "patch"])
    def me(self, request):
        facility = get_facility_for_user(request.user)
        if not facility:
            return Response({"error": "Facility profile not found"}, status=status.HTTP_404_NOT_FOUND)

        if request.method == "PATCH":
            serializer = self.get_serializer(facility, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)

        serializer = self.get_serializer(facility)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def dashboard(self, request):
        """Aggregated dashboard stats for the facility."""
        facility = get_facility_for_user(request.user)
        if not facility:
            return Response({"error": "Facility profile not found"}, status=status.HTTP_404_NOT_FOUND)

        today = timezone.now().date()

        patient_ids = FacilityPatientAccess.objects.filter(
            facility=facility, is_active=True
        ).values_list("patient_id", flat=True)

        total_patients = len(patient_ids)

        appointments_today = FacilityAppointment.objects.filter(
            facility=facility, date=today
        ).count()

        pending_appointments = FacilityAppointment.objects.filter(
            facility=facility, date=today, status=FacilityAppointment.Status.PENDING
        ).count()

        active_staff = facility.staff_members.filter(is_active=True).count()

        total_beds = Bed.objects.filter(ward__facility=facility).count()
        occupied_beds = Bed.objects.filter(ward__facility=facility, status=Bed.BedStatus.OCCUPIED).count()

        pending_lab_tests = LabTest.objects.filter(
            facility=facility, status__in=["pending", "sample_collected", "processing"]
        ).count()

        recent_appointments = FacilityAppointment.objects.filter(
            facility=facility
        ).select_related("patient", "provider").order_by("-date", "-start_time")[:5]

        recent_appt_data = FacilityAppointmentSerializer(recent_appointments, many=True).data

        return Response({
            "total_patients": total_patients,
            "appointments_today": appointments_today,
            "pending_appointments": pending_appointments,
            "active_staff": active_staff,
            "total_beds": total_beds,
            "occupied_beds": occupied_beds,
            "available_beds": total_beds - occupied_beds,
            "bed_occupancy_rate": round((occupied_beds / total_beds * 100), 1) if total_beds else 0,
            "pending_lab_tests": pending_lab_tests,
            "recent_appointments": recent_appt_data,
        })


class LocumViewSet(viewsets.ModelViewSet):
    queryset = Locum.objects.all()
    serializer_class = LocumSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["profession", "is_available", "region", "district"]
    search_fields = ["full_name", "email", "license_number"]
    ordering_fields = ["created_at", "years_of_experience", "full_name"]
    ordering = ["-created_at"]


class StaffViewSet(viewsets.ModelViewSet):
    queryset = FacilityStaff.objects.all()
    serializer_class = FacilityStaffSerializer
    permission_classes = [IsFacilityUser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["profession", "department", "is_active"]
    search_fields = ["full_name", "employee_id", "position", "email"]
    ordering_fields = ["created_at", "hire_date", "full_name"]
    ordering = ["-created_at"]

    def get_queryset(self):
        facility = get_facility_for_user(self.request.user)
        if facility:
            return FacilityStaff.objects.filter(facility=facility).select_related("user")
        return FacilityStaff.objects.none()

    def perform_create(self, serializer):
        import secrets as _secrets
        from accounts.models import CustomUser
        from django.conf import settings as _settings

        facility = get_facility_for_user(self.request.user)
        staff = serializer.save(facility=facility)

        if staff.email:
            temp_password = _secrets.token_urlsafe(10)
            name_parts = (staff.full_name or "").split()
            user, created = CustomUser.objects.get_or_create(
                email=staff.email,
                defaults={
                    "username": staff.email,
                    "first_name": name_parts[0] if name_parts else "",
                    "last_name": " ".join(name_parts[1:]) if len(name_parts) > 1 else "",
                },
            )
            if created:
                user.set_password(temp_password)
                user.save()
                staff.user = user
                staff.save(update_fields=["user"])

                generic_send_mail.delay(
                    recipient=staff.email,
                    title=f"Your BridgeCare Staff Account — {facility.name}",
                    payload={
                        "user_name": staff.full_name,
                        "organization_name": facility.name,
                        "email": staff.email,
                        "password": temp_password,
                        "phone_number": str(staff.phone_number) if staff.phone_number else "N/A",
                        "login_link": f"{_settings.FRONTEND_URL}/login",
                    },
                    email_type="staff_account_created",
                )

    @action(detail=False, methods=["post"], url_path="invite")
    def invite(self, request):
        facility = get_facility_for_user(request.user)
        if not facility:
            return Response({"error": "Facility not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = InviteStaffSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Cancel any existing pending invitation for this email at this facility
        StaffInvitation.objects.filter(
            facility=facility, email=data["email"], status=StaffInvitation.Status.PENDING
        ).update(status=StaffInvitation.Status.CANCELLED)

        token = secrets.token_urlsafe(32)
        invitation = StaffInvitation.objects.create(
            facility=facility,
            email=data["email"],
            full_name=data["full_name"],
            profession=data["profession"],
            position=data.get("position", ""),
            department=data.get("department", ""),
            token=token,
            expires_at=timezone.now() + timedelta(days=7),
        )

        from django.conf import settings
        invite_link = f"{settings.FRONTEND_URL}/signup/facility-staff?token={token}"
        generic_send_mail.delay(
            recipient=data["email"],
            title=f"You've been invited to join {facility.name} on BridgeCare",
            payload={
                "user_name": data["full_name"],
                "facility_name": facility.name,
                "invite_link": invite_link,
            },
            email_type="staff_invitation",
        )

        return Response(StaffInvitationSerializer(invitation).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"], url_path="invitations")
    def invitations(self, request):
        facility = get_facility_for_user(request.user)
        invitations = StaffInvitation.objects.filter(facility=facility).order_by("-created_at")
        return Response(StaffInvitationSerializer(invitations, many=True).data)


class PatientView(APIView):
    """Manage facility patients — list, register, bulk upload."""

    permission_classes = [IsFacilityUser]

    @extend_schema(
        parameters=[
            OpenApiParameter(name="search", type={"type": "string"}, location=OpenApiParameter.QUERY, required=False),
            OpenApiParameter(name="page", type={"type": "integer"}, location=OpenApiParameter.QUERY, required=False),
        ],
        responses={200: PatientProfileListSerializer(many=True)},
    )
    def get(self, request):
        facility = get_facility_for_user(request.user)

        patient_ids = FacilityPatientAccess.objects.filter(
            facility=facility, is_active=True
        ).values_list("patient_id", flat=True)

        patient_profiles = PatientProfile.objects.filter(id__in=patient_ids)

        search_query = request.query_params.get("search", "").strip()
        if search_query:
            search_filter = (
                Q(first_name__icontains=search_query)
                | Q(last_name__icontains=search_query)
                | Q(email__icontains=search_query)
                | Q(phone_number__icontains=search_query)
                | Q(patient_id__icontains=search_query)
            )
            patient_profiles = patient_profiles.filter(search_filter)

        paginator = PageNumberPagination()
        paginator.page_size = 50
        paginated_qs = paginator.paginate_queryset(patient_profiles, request)
        serializer = PatientProfileListSerializer(paginated_qs, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        """Register a new walk-in patient and link to this facility."""
        facility = get_facility_for_user(request.user)

        serializer = RegisterPatientSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        patient = PatientProfile.objects.create(
            first_name=data["first_name"],
            last_name=data["last_name"],
            other_names=data.get("other_names", ""),
            date_of_birth=data.get("date_of_birth"),
            gender=data.get("gender", ""),
            phone_number=data.get("phone_number") or None,
            email=data.get("email") or None,
            address=data.get("address", ""),
            blood_type=data.get("blood_type", ""),
            insurance_provider=data.get("insurance_provider", ""),
            insurance_number=data.get("insurance_number", ""),
            emergency_contact_name=data.get("emergency_contact_name", ""),
            emergency_contact_phone=data.get("emergency_contact_phone") or None,
            emergency_contact_relationship=data.get("emergency_contact_relationship", ""),
        )

        FacilityPatientAccess.objects.get_or_create(
            facility=facility,
            patient=patient,
            defaults={"is_active": True},
        )

        return Response(PatientProfileSerializer(patient).data, status=status.HTTP_201_CREATED)


class WardViewSet(viewsets.ModelViewSet):
    permission_classes = [IsFacilityUser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["ward_type", "is_active"]
    search_fields = ["name"]

    def get_serializer_class(self):
        return WardSerializer

    def get_queryset(self):
        facility = get_facility_for_user(self.request.user)
        if facility:
            return Ward.objects.filter(facility=facility).prefetch_related("beds")
        return Ward.objects.none()

    def perform_create(self, serializer):
        facility = get_facility_for_user(self.request.user)
        serializer.save(facility=facility)

    @action(detail=True, methods=["post"], url_path="add-bed")
    def add_bed(self, request, pk=None):
        ward = self.get_object()
        bed_number = request.data.get("bed_number")
        if not bed_number:
            return Response({"error": "bed_number is required"}, status=status.HTTP_400_BAD_REQUEST)

        if Bed.objects.filter(ward=ward, bed_number=bed_number).exists():
            return Response({"error": "Bed number already exists in this ward"}, status=status.HTTP_400_BAD_REQUEST)

        bed = Bed.objects.create(ward=ward, bed_number=bed_number)
        return Response(BedSerializer(bed).data, status=status.HTTP_201_CREATED)


class BedViewSet(viewsets.ModelViewSet):
    serializer_class = BedSerializer
    permission_classes = [IsFacilityUser]

    def get_queryset(self):
        facility = get_facility_for_user(self.request.user)
        if facility:
            return Bed.objects.filter(ward__facility=facility).select_related("patient", "ward")
        return Bed.objects.none()

    @action(detail=True, methods=["post"], url_path="admit")
    def admit_patient(self, request, pk=None):
        bed = self.get_object()
        if bed.status == Bed.BedStatus.OCCUPIED:
            return Response({"error": "Bed is already occupied"}, status=status.HTTP_400_BAD_REQUEST)

        patient_id = request.data.get("patient_id")
        if not patient_id:
            return Response({"error": "patient_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            patient = PatientProfile.objects.get(id=patient_id)
        except PatientProfile.DoesNotExist:
            return Response({"error": "Patient not found"}, status=status.HTTP_404_NOT_FOUND)

        bed.patient = patient
        bed.status = Bed.BedStatus.OCCUPIED
        bed.admitted_at = timezone.now()
        bed.notes = request.data.get("notes", "")
        bed.save()
        return Response(BedSerializer(bed).data)

    @action(detail=True, methods=["post"], url_path="discharge")
    def discharge_patient(self, request, pk=None):
        bed = self.get_object()
        bed.patient = None
        bed.status = Bed.BedStatus.AVAILABLE
        bed.admitted_at = None
        bed.save()
        return Response(BedSerializer(bed).data)

    @action(detail=True, methods=["post"], url_path="maintenance")
    def set_maintenance(self, request, pk=None):
        bed = self.get_object()
        bed.status = Bed.BedStatus.MAINTENANCE
        bed.save()
        return Response(BedSerializer(bed).data)


class FacilityAppointmentViewSet(viewsets.ModelViewSet):
    serializer_class = FacilityAppointmentSerializer
    permission_classes = [IsFacilityUser]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["status", "appointment_type", "consultation_type", "date", "provider"]
    ordering_fields = ["date", "start_time", "created_at"]
    ordering = ["date", "start_time"]

    def get_queryset(self):
        facility = get_facility_for_user(self.request.user)
        if facility:
            qs = FacilityAppointment.objects.filter(facility=facility).select_related("patient", "provider")
            # Filter by date range
            start = self.request.query_params.get("start_date")
            end = self.request.query_params.get("end_date")
            if start:
                qs = qs.filter(date__gte=start)
            if end:
                qs = qs.filter(date__lte=end)
            return qs
        return FacilityAppointment.objects.none()

    def perform_create(self, serializer):
        facility = get_facility_for_user(self.request.user)
        serializer.save(facility=facility)

    @action(detail=True, methods=["post"], url_path="change-status")
    def change_status(self, request, pk=None):
        appointment = self.get_object()
        new_status = request.data.get("status")
        if new_status not in FacilityAppointment.Status.values:
            return Response({"error": f"Invalid status. Choices: {FacilityAppointment.Status.values}"}, status=status.HTTP_400_BAD_REQUEST)
        appointment.status = new_status
        appointment.save()
        return Response(FacilityAppointmentSerializer(appointment).data)


class LabTestViewSet(viewsets.ModelViewSet):
    serializer_class = LabTestSerializer
    permission_classes = [IsFacilityUser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["status", "test_category", "patient"]
    search_fields = ["test_name", "patient__patient_id", "patient__first_name", "patient__last_name"]

    def get_queryset(self):
        facility = get_facility_for_user(self.request.user)
        if facility:
            return LabTest.objects.filter(facility=facility).select_related("patient", "ordered_by")
        return LabTest.objects.none()

    def perform_create(self, serializer):
        facility = get_facility_for_user(self.request.user)
        serializer.save(facility=facility)

    @action(detail=True, methods=["post"], url_path="update-result")
    def update_result(self, request, pk=None):
        lab_test = self.get_object()
        lab_test.result = request.data.get("result", lab_test.result)
        lab_test.reference_range = request.data.get("reference_range", lab_test.reference_range)
        lab_test.notes = request.data.get("notes", lab_test.notes)
        if request.data.get("status"):
            lab_test.status = request.data["status"]
        if lab_test.status == LabTest.Status.COMPLETED and not lab_test.resulted_at:
            lab_test.resulted_at = timezone.now()
        lab_test.save()
        return Response(LabTestSerializer(lab_test).data)
