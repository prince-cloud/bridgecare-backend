from rest_framework.routers import DefaultRouter
from . import views
from django.urls import path

app_name = "professionals"

router = DefaultRouter()
router.register(r"profiles", views.ProfessionalProfileViewSet, basename="profile")
router.register(r"professions", views.ProfessionsViewSet, basename="profession")
router.register(
    r"specializations", views.SpecializationViewSet, basename="specialization"
)
router.register(
    r"licence-issue-authorities",
    views.LicenceIssueAuthorityViewSet,
    basename="licence-issue-authority",
)
urlpatterns = [
    path(
        "locum-applications/",
        views.LocumApplicationsView.as_view(),
        name="locum-applications",
    ),
]
urlpatterns = urlpatterns + router.urls
