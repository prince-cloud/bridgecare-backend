from rest_framework.routers import DefaultRouter
from . import views

app_name = "patients"

router = DefaultRouter()
router.register(r"profiles", views.PatientProfileViewSet, basename="profile")

urlpatterns = router.urls

