from rest_framework.routers import DefaultRouter
from django.urls import path, include
from . import views

app_name = "communities"

# Create router for all ViewSets
router = DefaultRouter()

# Register all ViewSets
router.register(r"organizations", views.OrganizationViewSet, basename="organization")
router.register(r"programs", views.HealthProgramViewSet, basename="program")
router.register(
    r"interventions", views.ProgramInterventionViewSet, basename="intervention"
)
router.register(
    r"bulk-intervention-uploads",
    views.BulkInterventionUploadViewSet,
    basename="bulk-intervention-upload",
)

router.register(
    r"bulk-survey-uploads",
    views.BulkSurveyUploadViewSet,
    basename="bulk-survey-upload",
)
router.register(r"analytics", views.CommunityAnalyticsViewSet, basename="analytics")
router.register("survey", views.SurveyViewset, basename="survey")
router.register(
    "survey-response", views.SurveyResponseViewset, basename="survey-response"
)
urlpatterns = [
    path("survey-create/", views.SurveyCreateView.as_view(), name="create-survey"),
    path("survey-answer/", views.SurveyAnswerView.as_view(), name="survey-answer"),
]

urlpatterns += router.urls
