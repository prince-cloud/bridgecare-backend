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
router.register(
    "availability-blocks",
    views.AvailabilityBlockViewSet,
    basename="availability-block",
)
router.register("break-periods", views.BreakPeriodViewSet, basename="break-period")
router.register(
    "education-histories",
    views.EducationHistoryVieset,
    basename="education-history",
)
urlpatterns = [
    path(
        "locum-applications/",
        views.LocumApplicationsView.as_view(),
        name="locum-applications",
    ),
    path(
        "availability/",
        views.AvailabilityView.as_view(),
        name="availability",
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
    path(
        "patients/",
        views.PatientView.as_view(),
        name="patients",
    ),
    path(
        "dashboard-statistics/",
        views.DashboardStatisticsView.as_view(),
        name="dashboard-statistics",
    ),
]
urlpatterns = urlpatterns + router.urls
