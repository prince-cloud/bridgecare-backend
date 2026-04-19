from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import CustomUser
from patients.models import PatientProfile


class CreatePatientUserViewTests(APITestCase):
    def test_create_patient_user_creates_profile_without_signal_dependency(self):
        payload = {
            "email": "patient@example.com",
            "phone_number": "+233201234567",
            "password": "strong-pass-123",
            "first_name": "Ama",
            "last_name": "Mensah",
            "date_of_birth": "1994-02-10",
            "gender": "F",
            "address": "Accra",
        }

        response = self.client.post(reverse("create_patient_user"), payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = CustomUser.objects.get(email=payload["email"])
        profile = PatientProfile.objects.get(user=user)
        self.assertEqual(profile.first_name, payload["first_name"])
        self.assertEqual(profile.last_name, payload["last_name"])
        self.assertEqual(profile.surname, payload["last_name"])
        self.assertEqual(profile.email, payload["email"])
        self.assertEqual(str(user.default_profile), str(profile.id))
