from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import CustomUser
from professionals.models import (
    Availability,
    Profession,
    ProfessionalProfile,
    Specialization,
)


class PublicHealthProfessionalSearchTests(APITestCase):
    """
    QA finding MSG-02: the patient "New Conversation" search sends `?search=`
    to this endpoint. The viewset listed `SearchFilter` but had no
    `search_fields`, so DRF ignored the query and returned every professional.
    """

    def setUp(self):
        self.url = "/appapi/v1/health-professionals/"
        nurse = Profession.objects.create(name="Nurse")
        doctor = Profession.objects.create(name="Doctor")
        cardiology = Specialization.objects.create(name="Cardiology")
        self._make("Henry", "Karikari", doctor, cardiology)
        self._make("Ama", "Mensah", nurse, None)
        self._make("Kofi", "Boateng", doctor, None)

    def _make(self, first, last, profession, specialization):
        user = CustomUser.objects.create_user(
            username=f"{first.lower()}@example.com",
            email=f"{first.lower()}@example.com",
            password="pw-for-tests",
            first_name=first,
            last_name=last,
        )
        profile, _ = ProfessionalProfile.objects.get_or_create(user=user)
        profile.profession = profession
        profile.specialization = specialization
        profile.is_verified = True
        profile.save()
        Availability.objects.create(provider=profile, telehealth_availability=True)
        return profile

    def _names(self, response):
        return sorted(
            item["user"]["first_name"] for item in response.data["results"]
        )

    def test_search_by_first_name(self):
        response = self.client.get(self.url, {"search": "Hen"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self._names(response), ["Henry"])

    def test_search_by_last_name(self):
        response = self.client.get(self.url, {"search": "mensah"})
        self.assertEqual(self._names(response), ["Ama"])

    def test_search_by_specialization(self):
        response = self.client.get(self.url, {"search": "cardio"})
        self.assertEqual(self._names(response), ["Henry"])

    def test_search_by_profession(self):
        response = self.client.get(self.url, {"search": "doctor"})
        self.assertEqual(self._names(response), ["Henry", "Kofi"])

    def test_no_match_returns_empty_list(self):
        response = self.client.get(self.url, {"search": "zzz-nobody"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["results"], [])

    def test_without_search_returns_everyone(self):
        response = self.client.get(self.url)
        self.assertEqual(self._names(response), ["Ama", "Henry", "Kofi"])
