from rest_framework.routers import DefaultRouter
from django.urls import path, include
from . import views

app_name = "communities"

# Create router for all ViewSets
router = DefaultRouter()

# Register all ViewSets
router.register(r"organizations", views.OrganizationViewSet, basename="organization")
router.register("staff", views.StaffViewSet, basename="staff")
router.register(
    r"program-types", views.HealthProgramTypeViewSet, basename="program-type"
)
router.register(
    r"intervention-types",
    views.ProgramInterventionTypeViewSet,
    basename="intervention-type",
)
router.register(r"programs", views.HealthProgramViewSet, basename="program")
router.register(
    r"interventions", views.ProgramInterventionViewSet, basename="intervention"
)
router.register(
    r"intervention-responses",
    views.InterventionResponseViewSet,
    basename="intervention-response",
)
router.register(
    "intervention-fields", views.InterventionFieldViewSet, basename="intervention-field"
)
router.register(
    r"locum-job-roles", views.LocumJobRoleViewSet, basename="locum-job-role"
)
router.register(r"locum-jobs", views.LocumJobViewSet, basename="locum-job")
router.register(
    r"locum-job-applications",
    views.LocumJobApplicationViewSet,
    basename="locum-job-application",
)
router.register(
    r"health-program-partners",
    views.HealthProgramPartnersViewSet,
    basename="health-program-partner",
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
    # Survey API endpoints
    path("survey-create/", views.SurveyCreateView.as_view(), name="create-survey"),
    path("survey-answer/", views.SurveyAnswerView.as_view(), name="survey-answer"),
    # Program Intervention API endpoints (similar to Survey)
    path(
        "intervention-create/",
        views.InterventionCreateView.as_view(),
        name="create-intervention",
    ),
    path(
        "intervention-answer/",
        views.InterventionAnswerView.as_view(),
        name="intervention-answer",
    ),
    path(
        "intervention-answer/<uuid:response_id>/",
        views.InterventionAnswerUpdateView.as_view(),
        name="intervention-answer-update",
    ),
    path(
        "dashboard-statistics/",
        views.DashboardStatisticsView.as_view(),
        name="dashboard-statistics",
    ),
]

urlpatterns += router.urls
