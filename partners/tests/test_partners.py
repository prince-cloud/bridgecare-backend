from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import CustomUser
from partners.models import PartnerProfile, Subsidy


class SubsidyApiTests(APITestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username="partner-user",
            email="partner@example.com",
            password="strong-pass-123",
        )
        self.partner = PartnerProfile.objects.create(
            user=self.user,
            organization_name="BridgeCare Partner",
            is_verified=True,
        )
        self.client.force_authenticate(self.user)

    def test_create_subsidy_accepts_cash_grant_type(self):
        payload = {
            "name": "New Subsidy",
            "subsidy_type": "cash_grant",
            "total_budget": "120.00",
            "budget_used": "0.00",
            "target": "The needy",
            "start_date": "2026-04-30",
            "end_date": "2026-07-30",
            "status": "active",
            "notes": "",
        }

        response = self.client.post(reverse("partners:subsidy-list"), payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["subsidy_type"], Subsidy.SubsidyType.CASH_GRANT)
        self.assertEqual(Subsidy.objects.count(), 1)
        self.assertEqual(Subsidy.objects.get().partner, self.partner)
