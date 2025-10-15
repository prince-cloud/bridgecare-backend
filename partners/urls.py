from rest_framework.routers import DefaultRouter
from . import views

app_name = "partners"

router = DefaultRouter()
router.register(r"profiles", views.PartnerProfileViewSet, basename="profile")

urlpatterns = router.urls

