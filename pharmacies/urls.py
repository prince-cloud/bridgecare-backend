from rest_framework.routers import DefaultRouter
from . import views

app_name = "pharmacies"

router = DefaultRouter()
router.register("profiles", views.PharmacyProfileViewSet, basename="profile")
router.register("inventory", views.InventoryViewSet, basename="inventory")

urlpatterns = router.urls
