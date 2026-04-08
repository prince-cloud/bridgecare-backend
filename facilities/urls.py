from django.urls import path
from rest_framework.routers import DefaultRouter
from . import views

app_name = "facilities"

router = DefaultRouter()
router.register(
    r"facility-profiles", views.FacilityProfileViewSet, basename="facility-profile"
)
router.register(r"locums", views.LocumViewSet, basename="locum")
router.register(r"staff", views.StaffViewSet, basename="staff")

urlpatterns = [
    path("patients/", views.PatientView.as_view(), name="patient"),
]

urlpatterns += router.urls
