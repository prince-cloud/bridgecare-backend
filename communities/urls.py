from rest_framework.routers import DefaultRouter
from django.urls import path, include
from . import views

app_name = "communities"

# Create router for all ViewSets
router = DefaultRouter()

# Register all ViewSets
router.register(r"profiles", views.CommunityProfileViewSet, basename="profile")
router.register(r"programs", views.HealthProgramViewSet, basename="program")
router.register(
    r"interventions", views.ProgramInterventionViewSet, basename="intervention"
)
router.register(
    r"bulk-intervention-uploads",
    views.BulkInterventionUploadViewSet,
    basename="bulk-intervention-upload",
)
router.register(r"surveys", views.HealthSurveyViewSet, basename="survey")
router.register(
    r"survey-responses", views.SurveyResponseViewSet, basename="survey-response"
)
router.register(
    r"bulk-survey-uploads",
    views.BulkSurveyUploadViewSet,
    basename="bulk-survey-upload",
)
router.register(r"reports", views.ProgramReportViewSet, basename="report")
router.register(r"analytics", views.CommunityAnalyticsViewSet, basename="analytics")

urlpatterns = router.urls

