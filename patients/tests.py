from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import CustomUser
from patients.models import PatientProfile, Prescription, Visitation, Vitals
from professionals.models import ProfessionalProfile


class PatientReadsOwnRecordsTests(APITestCase):
    """
    Tech report 18.08.2026, item 1.2: the patient dashboard showed no vitals
    or prescriptions. The endpoints required a professional or facility
    profile even for GET, so a patient got 403 on their own records.
    """

    def setUp(self):
        self.patient_user = CustomUser.objects.create_user(
            username="ama@example.com", email="ama@example.com", password="pw-for-tests"
        )
        self.patient, _ = PatientProfile.objects.get_or_create(user=self.patient_user)

        other_user = CustomUser.objects.create_user(
            username="kofi@example.com", email="kofi@example.com", password="pw-for-tests"
        )
        self.other_patient, _ = PatientProfile.objects.get_or_create(user=other_user)

        doctor_user = CustomUser.objects.create_user(
            username="doc@example.com", email="doc@example.com", password="pw-for-tests"
        )
        self.doctor, _ = ProfessionalProfile.objects.get_or_create(user=doctor_user)

        self.visit = Visitation.objects.create(
            patient=self.patient, issued_by=self.doctor, title="Check-up"
        )
        self.vitals = Vitals.objects.create(
            visitation=self.visit, height="170", weight="65", blood_pressure="120/80"
        )
        self.rx = Prescription.objects.create(
            visitation=self.visit, medication="Paracetamol", dosage="500 mg"
        )

        other_visit = Visitation.objects.create(
            patient=self.other_patient, issued_by=self.doctor, title="Other"
        )
        Vitals.objects.create(visitation=other_visit, height="180")
        Prescription.objects.create(visitation=other_visit, medication="Ibuprofen")

    def _results(self, response):
        data = response.data
        return data["results"] if isinstance(data, dict) and "results" in data else data

    def test_patient_can_read_own_vitals(self):
        self.client.force_authenticate(self.patient_user)
        response = self.client.get("/patients/vitals/")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        ids = {str(item["id"]) for item in self._results(response)}
        self.assertEqual(ids, {str(self.vitals.id)})

    def test_patient_can_read_own_prescriptions(self):
        self.client.force_authenticate(self.patient_user)
        response = self.client.get("/patients/prescriptions/")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        meds = {item["medication"] for item in self._results(response)}
        self.assertEqual(meds, {"Paracetamol"})

    def test_patient_cannot_write_records(self):
        self.client.force_authenticate(self.patient_user)
        response = self.client.post(
            "/patients/vitals/", {"visitation": str(self.visit.id), "height": "999"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Vitals.objects.filter(visitation=self.visit).count(), 1)

    def test_anonymous_is_rejected(self):
        response = self.client.get("/patients/vitals/")
        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    def test_professional_still_writes(self):
        self.client.force_authenticate(self.doctor.user)
        response = self.client.post(
            "/patients/vitals/", {"visitation": str(self.visit.id), "height": "171"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
