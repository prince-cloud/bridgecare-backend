from rest_framework.routers import DefaultRouter
from . import views

app_name = "api-urls"

router = DefaultRouter()
router.register("locum-jobs", views.LocumJobsViewset, basename="locumjob")
router.register(
    "health-professionals",
    views.ProfessionalProfileViewSet,
    basename="health-professionals",
)

urlpatterns = router.urls
