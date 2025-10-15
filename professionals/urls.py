from rest_framework.routers import DefaultRouter
from . import views

app_name = "professionals"

router = DefaultRouter()
router.register(r"profiles", views.ProfessionalProfileViewSet, basename="profile")

urlpatterns = router.urls

