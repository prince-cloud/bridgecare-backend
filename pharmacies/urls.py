from rest_framework.routers import DefaultRouter
from . import views

app_name = "pharmacies"

router = DefaultRouter()
router.register(r"profiles", views.PharmacyProfileViewSet, basename="profile")

urlpatterns = router.urls

