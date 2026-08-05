from django.urls import path
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
router.register("inventory", views.InventoryViewSet, basename="inventory")
router.register(
    "health-programs", views.HealthProgramViewSet, basename="health-programs"
)
urlpatterns = router.urls + [
    path("contact/", views.ContactEnquiryView.as_view(), name="contact-enquiry"),
]
