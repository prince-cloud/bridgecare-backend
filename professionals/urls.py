from rest_framework.routers import DefaultRouter
from . import views

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
urlpatterns = router.urls
