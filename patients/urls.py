from rest_framework.routers import DefaultRouter
from . import views

app_name = "patients"

router = DefaultRouter()
router.register(r"profiles", views.PatientProfileViewSet, basename="profile")
router.register("visitation", views.VisitationViewSet, basename="visitation")

urlpatterns = router.urls
