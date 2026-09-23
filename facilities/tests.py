from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import CustomUser
from facilities.models import Bed, FacilityProfile, Ward


class WardCreationTests(APITestCase):
    """
    QA finding FAC-01: a ward created with a capacity must get that many beds
    at once. Staff used to add every bed by hand afterwards.
    """

    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username="facility@example.com",
            email="facility@example.com",
            password="pw-for-tests",
        )
        self.facility = FacilityProfile.objects.create(
            user=self.user,
            name="Ridge Hospital",
            facility_type="hospital",
            address="Accra",
            district="Accra Metro",
            region="Greater Accra",
        )
        self.client.force_authenticate(self.user)
        self.url = "/facilities/wards/"

    def test_ward_with_capacity_gets_numbered_beds(self):
        response = self.client.post(
            self.url,
            {"name": "Ward A", "ward_type": "general", "capacity": 12},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        ward = Ward.objects.get(id=response.data["id"])
        beds = list(ward.beds.order_by("created_at", "bed_number"))
        self.assertEqual(len(beds), 12)
        self.assertEqual(
            sorted(int(bed.bed_number) for bed in beds), list(range(1, 13))
        )
        self.assertTrue(all(bed.status == Bed.BedStatus.AVAILABLE for bed in beds))
        # The response already reflects the beds so the client needs no refetch.
        self.assertEqual(response.data["total_beds"], 12)
        self.assertEqual(response.data["available_beds"], 12)

    def test_ward_without_capacity_gets_no_beds(self):
        response = self.client.post(
            self.url, {"name": "Ward B", "ward_type": "general"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(Bed.objects.filter(ward_id=response.data["id"]).count(), 0)

    def test_capacity_above_the_cap_is_rejected_with_a_readable_message(self):
        response = self.client.post(
            self.url,
            {"name": "Ward C", "ward_type": "general", "capacity": 2000},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Ward.objects.count(), 0)
        self.assertIn("capacity", response.data)
        self.assertEqual(
            response.data["errorMsg"], "Capacity: A ward can have at most 500 beds."
        )

    def test_add_bed_still_rejects_a_duplicate_number(self):
        create = self.client.post(
            self.url,
            {"name": "Ward D", "ward_type": "general", "capacity": 2},
            format="json",
        )
        ward_id = create.data["id"]

        response = self.client.post(
            f"{self.url}{ward_id}/add-bed/", {"bed_number": "1"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Bed.objects.filter(ward_id=ward_id).count(), 2)
