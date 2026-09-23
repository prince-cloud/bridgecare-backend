"""Tests for the admin_api surface.

Covers the platform-admin gate, per-model RBAC, CRUD + audit logging,
list features (search/filter/order/pagination/facets), custom actions,
FK label annotation, the recent-actions feed, and a URL smoke test that
hits every registered resource and dashboard endpoint.

Run with: ./env/bin/python manage.py test admin_api
"""

from django.contrib.admin.models import ADDITION, CHANGE, DELETION, LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import override_settings
from rest_framework.test import APITestCase

from communities.models import HealthProgram, HealthProgramType

from .urls import dashboard_urls, router

User = get_user_model()


def superuser(email="root@example.com"):
    return User.objects.create_user(
        username=email, email=email, password="x", is_staff=True, is_superuser=True
    )


def staffuser(email="staffer@example.com"):
    return User.objects.create_user(username=email, email=email, password="x", is_staff=True)


class PlatformGateTests(APITestCase):
    """IsPlatformAdmin is the outer gate; AdminModelPermission is the inner one."""

    def test_anonymous_is_unauthorized(self):
        res = self.client.get("/admin-api/health-programs/")
        self.assertEqual(res.status_code, 401)

    def test_non_staff_is_forbidden(self):
        plain = User.objects.create_user(username="plain@example.com", email="plain@example.com", password="x")
        self.client.force_authenticate(plain)
        res = self.client.get("/admin-api/health-programs/")
        self.assertEqual(res.status_code, 403)

    @override_settings(ADMIN_API_REQUIRE_MODEL_PERMS=True)
    def test_staff_without_model_permission_is_forbidden(self):
        self.client.force_authenticate(staffuser())
        res = self.client.get("/admin-api/health-programs/")
        self.assertEqual(res.status_code, 403)

    @override_settings(ADMIN_API_REQUIRE_MODEL_PERMS=True)
    def test_staff_with_model_permission_is_allowed(self):
        user = staffuser()
        user.user_permissions.add(Permission.objects.get(codename="view_healthprogram"))
        self.client.force_authenticate(user)
        res = self.client.get("/admin-api/health-programs/")
        self.assertEqual(res.status_code, 200)

    @override_settings(ADMIN_API_REQUIRE_MODEL_PERMS=True)
    def test_view_permission_does_not_grant_create(self):
        user = staffuser()
        user.user_permissions.add(Permission.objects.get(codename="view_healthprogram"))
        self.client.force_authenticate(user)
        res = self.client.post("/admin-api/health-programs/", {}, format="json")
        self.assertEqual(res.status_code, 403)

    @override_settings(ADMIN_API_REQUIRE_MODEL_PERMS=True)
    def test_superuser_bypasses_model_permissions(self):
        self.client.force_authenticate(superuser())
        res = self.client.get("/admin-api/health-programs/")
        self.assertEqual(res.status_code, 200)

    @override_settings(ADMIN_API_REQUIRE_MODEL_PERMS=False)
    def test_flag_off_falls_back_to_platform_gate_only(self):
        self.client.force_authenticate(staffuser())
        res = self.client.get("/admin-api/health-programs/")
        self.assertEqual(res.status_code, 200)

    def test_me_returns_portal_format_permissions(self):
        user = staffuser()
        user.user_permissions.add(
            Permission.objects.get(codename="view_healthprogram"),
            Permission.objects.get(codename="change_healthprogram"),
        )
        self.client.force_authenticate(user)
        res = self.client.get("/admin-api/me/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("communities.healthprogram.view", res.data["permissions"])
        self.assertIn("communities.healthprogram.change", res.data["permissions"])
        self.assertFalse(res.data["is_admin"])

    def test_me_flags_superuser(self):
        self.client.force_authenticate(superuser())
        res = self.client.get("/admin-api/me/")
        self.assertTrue(res.data["is_superuser"])
        self.assertTrue(res.data["is_admin"])
        # Superusers get the unfiltered portal UI; permission list is unused.
        self.assertEqual(res.data["permissions"], [])


class HealthProgramCrudTests(APITestCase):
    """CRUD through the API writes django.contrib.admin LogEntries, and the
    response carries human-readable FK labels."""

    def setUp(self):
        self.admin = superuser()
        self.client.force_authenticate(self.admin)
        self.program_type = HealthProgramType.objects.create(name="Vaccination Drive")

    def payload(self, **overrides):
        data = {
            "program_name": "Test Outreach",
            "program_type": self.program_type.pk,
            "start_date": "2026-10-01",
            "region": "Greater Accra",
            "district": "Accra",
            "location_name": "Test Site",
            "target_participants": 100,
            "actual_participants": 0,
        }
        data.update(overrides)
        return data

    def test_create_assigns_operator_and_logs_audit(self):
        res = self.client.post("/admin-api/health-programs/", self.payload(), format="json")
        self.assertEqual(res.status_code, 201, res.data)
        program = HealthProgram.objects.get(pk=res.data["id"])
        self.assertEqual(program.created_by, self.admin)
        self.assertEqual(program.status, "planning")  # model default applied
        entry = LogEntry.objects.get(object_id=str(program.pk))
        self.assertEqual(entry.action_flag, ADDITION)
        self.assertEqual(entry.user, self.admin)

    def test_create_response_carries_fk_label(self):
        res = self.client.post("/admin-api/health-programs/", self.payload(), format="json")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["program_type_label"], str(self.program_type))

    def test_update_logs_change(self):
        res = self.client.post("/admin-api/health-programs/", self.payload(), format="json")
        program_id = res.data["id"]
        res = self.client.patch(
            f"/admin-api/health-programs/{program_id}/", {"district": "Tema"}, format="json"
        )
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["district"], "Tema")
        entry = LogEntry.objects.filter(object_id=program_id, action_flag=CHANGE).first()
        self.assertIsNotNone(entry)
        self.assertIn("district", entry.change_message)

    def test_delete_logs_deletion(self):
        res = self.client.post("/admin-api/health-programs/", self.payload(), format="json")
        program_id = res.data["id"]
        res = self.client.delete(f"/admin-api/health-programs/{program_id}/")
        self.assertEqual(res.status_code, 204)
        self.assertFalse(HealthProgram.objects.filter(pk=program_id).exists())
        entry = LogEntry.objects.filter(object_id=program_id, action_flag=DELETION).first()
        self.assertIsNotNone(entry)

    def test_validation_error_returns_field_errors(self):
        res = self.client.post("/admin-api/health-programs/", {"program_name": ""}, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertIn("program_name", res.data)


class HealthProgramListTests(APITestCase):
    """Search, filters, ordering, pagination and facets on the list endpoint."""

    def setUp(self):
        self.admin = superuser()
        self.client.force_authenticate(self.admin)
        self.programs = [
            HealthProgram.objects.create(
                program_name="Accra Screening",
                start_date="2026-10-01",
                region="Greater Accra",
                district="Accra",
                location_name="Central",
                created_by=self.admin,
                status="planning",
                target_participants=50,
            ),
            HealthProgram.objects.create(
                program_name="Kumasi Education",
                start_date="2026-11-01",
                region="Ashanti",
                district="Kumasi",
                location_name="South",
                created_by=self.admin,
                status="approved",
                target_participants=80,
            ),
            HealthProgram.objects.create(
                program_name="Tamale Vaccination",
                start_date="2026-12-01",
                region="Northern",
                district="Tamale",
                location_name="North",
                created_by=self.admin,
                status="in_progress",
                target_participants=120,
            ),
        ]

    def test_list_is_paginated(self):
        res = self.client.get("/admin-api/health-programs/?page_size=2")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["count"], 3)
        self.assertEqual(len(res.data["results"]), 2)

    def test_search_matches_name(self):
        res = self.client.get("/admin-api/health-programs/?search=kumasi")
        self.assertEqual(res.data["count"], 1)
        self.assertEqual(res.data["results"][0]["program_name"], "Kumasi Education")

    def test_filter_by_field(self):
        res = self.client.get("/admin-api/health-programs/?region=Ashanti")
        self.assertEqual(res.data["count"], 1)
        res = self.client.get("/admin-api/health-programs/?status=planning")
        self.assertEqual(res.data["count"], 1)

    def test_ordering(self):
        res = self.client.get("/admin-api/health-programs/?ordering=program_name")
        names = [r["program_name"] for r in res.data["results"]]
        self.assertEqual(names, sorted(names))

    def test_facets_count_and_label(self):
        res = self.client.get("/admin-api/health-programs/facets/")
        self.assertEqual(res.status_code, 200)
        status = {o["value"]: o["count"] for o in res.data["status"]}
        self.assertEqual(status, {"planning": 1, "approved": 1, "in_progress": 1})
        region = {o["value"]: o["label"] for o in res.data["region"]}
        self.assertEqual(region["Ashanti"], "Ashanti")

    def test_facets_respond_to_search(self):
        res = self.client.get("/admin-api/health-programs/facets/?search=kumasi")
        status = {o["value"]: o["count"] for o in res.data["status"]}
        self.assertEqual(status, {"approved": 1})


class HealthProgramActionTests(APITestCase):
    """Custom domain actions (approve/reject/cancel) and the audit trail."""

    def setUp(self):
        self.admin = superuser()
        self.client.force_authenticate(self.admin)
        self.program = HealthProgram.objects.create(
            program_name="Action Target",
            start_date="2026-10-01",
            region="Greater Accra",
            district="Accra",
            location_name="Central",
            created_by=self.admin,
            status="planning",
            target_participants=10,
        )

    def _status(self):
        return HealthProgram.objects.get(pk=self.program.pk).status

    def test_approve(self):
        res = self.client.post(f"/admin-api/health-programs/{self.program.pk}/approve/")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(self._status(), "approved")

    def test_reject(self):
        res = self.client.post(f"/admin-api/health-programs/{self.program.pk}/reject/")
        self.assertEqual(self._status(), "rejected")

    def test_cancel(self):
        res = self.client.post(f"/admin-api/health-programs/{self.program.pk}/cancel/")
        self.assertEqual(self._status(), "cancelled")

    def test_unknown_action_is_not_routed(self):
        # Asserted at the resolver level: the dev 404 page needs a staticfiles
        # manifest the test environment doesn't have.
        from django.urls import Resolver404, resolve

        with self.assertRaises(Resolver404):
            resolve(f"/admin-api/health-programs/{self.program.pk}/frobnicate/")

    def test_action_writes_history(self):
        # The program is ORM-created (no "add" entry — only admin portal
        # mutations are audited); the approve action must write a change entry.
        self.client.post(f"/admin-api/health-programs/{self.program.pk}/approve/")
        res = self.client.get(f"/admin-api/health-programs/{self.program.pk}/history/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data[0]["action"], "change")
        self.assertIn("status", res.data[0]["message"])
        self.assertIn("approve", res.data[0]["message"])


class FkLabelAnnotationTests(APITestCase):
    """The label mixin annotates list and retrieve responses for every FK the
    serializer does not already label — so the portal never shows a raw UUID."""

    def setUp(self):
        self.admin = superuser()
        self.client.force_authenticate(self.admin)
        self.program_type = HealthProgramType.objects.create(name="Screening Day")
        self.program = HealthProgram.objects.create(
            program_name="Label Check",
            start_date="2026-10-01",
            region="Greater Accra",
            district="Accra",
            location_name="Central",
            created_by=self.admin,
            status="planning",
            target_participants=10,
            program_type=self.program_type,
        )

    def test_list_rows_carry_fk_labels(self):
        res = self.client.get("/admin-api/health-programs/")
        row = res.data["results"][0]
        self.assertEqual(row["program_type_label"], str(self.program_type))
        self.assertIsNone(row["organization_label"])  # null FK → null label

    def test_retrieve_carries_fk_labels(self):
        res = self.client.get(f"/admin-api/health-programs/{self.program.pk}/")
        self.assertEqual(res.data["program_type_label"], str(self.program_type))

    def test_mixin_does_not_double_label_existing_names(self):
        # HealthProgramSerializer provides `created_by_name`; the mixin must
        # leave it alone instead of adding a competing `created_by_label`.
        res = self.client.get(f"/admin-api/health-programs/{self.program.pk}/")
        self.assertIn("created_by_name", res.data)
        self.assertNotIn("created_by_label", res.data)


class RecentActionsTests(APITestCase):
    """The dashboard feed shows the operator's own LogEntries with portal keys."""

    def setUp(self):
        self.admin = superuser(email="feeder@example.com")
        self.client.force_authenticate(self.admin)

    def test_recent_actions_lists_own_mutations(self):
        self.client.post(
            "/admin-api/health-programs/",
            {
                "program_name": "Feed Check",
                "start_date": "2026-10-01",
                "region": "Greater Accra",
                "district": "Accra",
                "location_name": "Central",
                "target_participants": 10,
            },
            format="json",
        )
        res = self.client.get("/admin-api/recent-actions/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]["resource"], "health-programs")
        self.assertEqual(res.data[0]["action"], "add")
        self.assertEqual(res.data[0]["user_name"], str(self.admin))

    def test_limit_caps_results(self):
        for i in range(4):
            self.client.patch(
                f"/admin-api/health-programs/{self._program_id_for(i)}/", {"district": f"D{i}"}, format="json"
            )
        res = self.client.get("/admin-api/recent-actions/?limit=2")
        self.assertEqual(len(res.data), 2)

    def _program_id_for(self, i):
        return HealthProgram.objects.create(
            program_name=f"Feed {i}",
            start_date="2026-10-01",
            region="Greater Accra",
            district="Accra",
            location_name="Central",
            created_by=self.admin,
            target_participants=10,
        ).pk


class UrlCoverageSmokeTests(APITestCase):
    """Every registered resource and dashboard endpoint must answer a superuser
    list request with 200 — a wiring regression net for all 92 models."""

    def test_every_resource_lists(self):
        self.client.force_authenticate(superuser())
        failures = []
        for prefix, _viewset, _basename in router.registry:
            res = self.client.get(f"/admin-api/{prefix}/")
            if res.status_code != 200 or "results" not in res.data:
                failures.append(f"{prefix}: {res.status_code}")
        self.assertEqual(failures, [])

    def test_every_resource_exposes_facets(self):
        self.client.force_authenticate(superuser())
        failures = []
        for prefix, _viewset, _basename in router.registry:
            res = self.client.get(f"/admin-api/{prefix}/facets/")
            if res.status_code != 200:
                failures.append(f"{prefix}: {res.status_code}")
        self.assertEqual(failures, [])

    def test_dashboard_endpoints(self):
        self.client.force_authenticate(superuser())
        for url in dashboard_urls:
            res = self.client.get(f"/admin-api/{url.pattern}")
            self.assertEqual(res.status_code, 200, str(url.pattern))
