from rest_framework.routers import DefaultRouter
from . import views
from django.urls import path

app_name = "professionals"

router = DefaultRouter()
router.register("profiles", views.ProfessionalProfileViewSet, basename="profile")
router.register("professions", views.ProfessionsViewSet, basename="profession")
router.register(
    "specializations", views.SpecializationViewSet, basename="specialization"
)
router.register(
    "licence-issue-authorities",
    views.LicenceIssueAuthorityViewSet,
    basename="licence-issue-authority",
)
router.register("appointments", views.AppointmentViewSet, basename="appointment")
urlpatterns = [
    path(
        "locum-applications/",
        views.LocumApplicationsView.as_view(),
        name="locum-applications",
    ),
    path(
        "appointments/available-slots/",
        views.AvailableTimeSlotsView.as_view(),
        name="available-time-slots",
    ),
    path(
        "appointments/book/",
        views.AppointmentBookingView.as_view(),
        name="appointment-booking",
    ),
]
urlpatterns = urlpatterns + router.urls
