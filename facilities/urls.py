from django.urls import path
from rest_framework.routers import DefaultRouter
from . import views

app_name = "facilities"

router = DefaultRouter()
router.register(r"facility-profiles", views.FacilityProfileViewSet, basename="facility-profile")
router.register(r"locums", views.LocumViewSet, basename="locum")
router.register(r"staff", views.StaffViewSet, basename="staff")
router.register(r"wards", views.WardViewSet, basename="ward")
router.register(r"beds", views.BedViewSet, basename="bed")
router.register(r"appointments", views.FacilityAppointmentViewSet, basename="facility-appointment")
router.register(r"lab-tests", views.LabTestViewSet, basename="lab-test")

urlpatterns = [
    path("patients/", views.PatientView.as_view(), name="facility-patients"),
]

urlpatterns += router.urls
