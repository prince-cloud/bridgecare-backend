from rest_framework.routers import DefaultRouter
from . import views

app_name = "facilities"

router = DefaultRouter()
router.register(r"facilities", views.FacilityViewSet, basename="facility")
router.register(r"profiles", views.FacilityProfileViewSet, basename="profile")
router.register(r"locums", views.LocumViewSet, basename="locum")
router.register(r"staff", views.StaffViewSet, basename="staff")

urlpatterns = router.urls
