from rest_framework.routers import DefaultRouter
from . import views

app_name = "partners"

router = DefaultRouter()
router.register(r"profiles", views.PartnerProfileViewSet, basename="profile")
router.register(r"subsidies", views.SubsidyViewSet, basename="subsidy")
router.register(r"partnership-requests", views.ProgramPartnershipRequestViewSet, basename="partnership-request")
router.register(r"program-monitors", views.ProgramMonitorViewSet, basename="program-monitor")
router.register(r"programs/discover", views.PublicProgramViewSet, basename="discover-program")
router.register(r"discover-partners", views.DiscoverPartnersView, basename="discover-partner")

urlpatterns = router.urls
