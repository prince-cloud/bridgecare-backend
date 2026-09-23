from decimal import Decimal

from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import CustomUser
from pharmacies.models import Drug, DrugCategory, DrugUnit, PharmacyProfile


def make_pharmacy(email, license_no):
    user = CustomUser.objects.create(username=email, email=email)
    return PharmacyProfile.objects.create(
        user=user,
        pharmacy_name=f"Pharm {license_no}",
        pharmacy_license=license_no,
        address="123 Street",
        phone_number="+233200000000",
        is_verified=True,
    )


class DrugCategoryDefaultsTests(APITestCase):
    """
    Tech report 18.08.2026, item 2.2: system default categories that every
    pharmacy can choose from, next to the ones it adds itself.
    """

    def setUp(self):
        self.pharmacy = make_pharmacy("one@x.com", "LIC-1")
        self.other = make_pharmacy("two@x.com", "LIC-2")
        self.client.force_authenticate(self.pharmacy.user)
        self.url = "/pharmacies/categories/"

    def _rows(self, response):
        data = response.data
        return data["results"] if isinstance(data, dict) and "results" in data else data

    def test_defaults_exist_after_migration(self):
        names = set(DrugCategory.objects.filter(pharmacy__isnull=True).values_list("name", flat=True))
        self.assertIn("Antibiotics", names)
        self.assertIn("Vitamins & Supplements", names)
        self.assertGreaterEqual(len(names), 10)

    def test_list_shows_defaults_and_own_with_ownership_flag(self):
        DrugCategory.objects.create(pharmacy=self.pharmacy, name="House Brand")
        response = self.client.get(self.url, {"page_size": 100})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        by_name = {row["name"]: row for row in self._rows(response)}
        self.assertIn("Antibiotics", by_name)
        self.assertFalse(by_name["Antibiotics"]["is_owner"])
        self.assertTrue(by_name["House Brand"]["is_owner"])

    def test_pharmacy_can_add_its_own_category(self):
        response = self.client.post(self.url, {"name": "Herbal"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(DrugCategory.objects.get(name="Herbal").pharmacy, self.pharmacy)

    def test_default_cannot_be_changed_or_deleted(self):
        default = DrugCategory.objects.get(name="Antibiotics")
        patch = self.client.patch(f"{self.url}{default.id}/", {"name": "Mine"}, format="json")
        self.assertEqual(patch.status_code, status.HTTP_403_FORBIDDEN)
        delete = self.client.delete(f"{self.url}{default.id}/")
        self.assertEqual(delete.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(DrugCategory.objects.filter(id=default.id).exists())

    def test_another_pharmacys_category_cannot_be_changed(self):
        theirs = DrugCategory.objects.create(pharmacy=self.other, name="Theirs")
        response = self.client.delete(f"{self.url}{theirs.id}/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_category_in_use_cannot_be_deleted(self):
        mine = DrugCategory.objects.create(pharmacy=self.pharmacy, name="In use")
        Drug.objects.create(
            pharmacy=self.pharmacy,
            name="Paracetamol",
            category=mine,
            base_unit=DrugUnit.TABLET,
            unit_price=Decimal("10.00"),
        )
        response = self.client.delete(f"{self.url}{mine.id}/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("re-categorise", response.data["errorMsg"])
