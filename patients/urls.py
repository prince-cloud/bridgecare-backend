from rest_framework.routers import DefaultRouter
from . import views

app_name = "patients"

router = DefaultRouter()
router.register(r"profiles", views.PatientProfileViewSet, basename="profile")
router.register("visitation", views.VisitationViewSet, basename="visitation")

router.register(r"diagnoses", views.DiagnosisViewSet, basename="diagnosis")
router.register(r"vitals", views.VitalsViewSet, basename="vitals")
router.register(r"prescriptions", views.PrescriptionViewSet, basename="prescription")
router.register(r"allergies", views.AllergyViewSet, basename="allergy")
router.register(r"notes", views.NotesViewSet, basename="note")
router.register(
    r"medical-history", views.MedicalHistoryViewSet, basename="medical-history"
)

urlpatterns = router.urls
