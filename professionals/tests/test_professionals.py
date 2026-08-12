from django.test import TestCase

# Create your tests here.


class MyInterventionsTests(TestCase):
    """
    The professional's "Interventions" screen: every intervention they can work
    on, grouped by event, newest event first.
    """

    def setUp(self):
        from datetime import date, timedelta

        from accounts.models import CustomUser
        from communities.models import (
            HealthProgram,
            HealthProgramInvitation,
            Organization,
            ProgramIntervention,
            ProgramInterventionType,
        )
        from professionals.models import ProfessionalProfile

        self.HealthProgramInvitation = HealthProgramInvitation

        owner = CustomUser.objects.create_user(
            username="org@example.com", email="org@example.com", password="pw-for-tests"
        )
        self.org, _ = Organization.objects.get_or_create(user=owner)
        self.org.organization_name = "Outreach Org"
        self.org.save()

        self.doctor = CustomUser.objects.create_user(
            username="doc@example.com", email="doc@example.com", password="pw-for-tests"
        )
        ProfessionalProfile.objects.get_or_create(user=self.doctor)

        itype = ProgramInterventionType.objects.create(name="Screening")

        def make_program(name, start):
            program = HealthProgram.objects.create(
                organization=self.org,
                program_name=name,
                start_date=start,
                target_participants=10,
                location_name="Accra",
                created_by=owner,
            )
            intervention = ProgramIntervention.objects.create(
                intervention_type=itype, program=program, title=f"{name} — Station 1"
            )
            return program, intervention

        today = date.today()
        self.old_program, self.old_iv = make_program("Older Event", today - timedelta(days=30))
        self.new_program, self.new_iv = make_program("Newest Event", today)

        for program, intervention in (
            (self.old_program, self.old_iv),
            (self.new_program, self.new_iv),
        ):
            invitation = HealthProgramInvitation.objects.create(
                program=program,
                invited_to=self.doctor,
                invited_by=self.org,
                status=HealthProgramInvitation.InvitationStatus.ACCEPTED,
            )
            invitation.intervention.add(intervention)

    def _get(self):
        self.client.force_login(self.doctor)
        return self.client.get(
            "/professionals/health-program-invitations/my-interventions/"
        )

    def test_interventions_are_grouped_by_event(self):
        response = self._get()
        self.assertEqual(response.status_code, 200, response.content[:300])

        groups = response.json()["groups"]
        self.assertEqual(len(groups), 2)
        names = [group["program_name"] for group in groups]
        self.assertCountEqual(names, ["Newest Event", "Older Event"])

    def test_the_newest_event_comes_first(self):
        """The UI expands the first group, so ordering decides what opens."""
        groups = self._get().json()["groups"]
        self.assertEqual(groups[0]["program_name"], "Newest Event")

    def test_each_group_carries_its_interventions_and_a_count(self):
        groups = self._get().json()["groups"]
        newest = next(g for g in groups if g["program_name"] == "Newest Event")

        self.assertEqual(newest["intervention_count"], 1)
        self.assertEqual(
            newest["interventions"][0]["display_title"], "Newest Event — Station 1"
        )
        # Needed to build the record/responses links.
        self.assertEqual(newest["program_id"], str(self.new_program.id))

    def test_a_pending_invitation_is_excluded(self):
        """
        A pending invitation grants no right to record, so its interventions
        must not appear on a screen whose whole purpose is starting work.
        """
        self.HealthProgramInvitation.objects.filter(
            program=self.old_program
        ).update(status=self.HealthProgramInvitation.InvitationStatus.PENDING)

        groups = self._get().json()["groups"]
        self.assertEqual([g["program_name"] for g in groups], ["Newest Event"])

    def test_another_professionals_events_are_not_listed(self):
        from accounts.models import CustomUser
        from professionals.models import ProfessionalProfile

        stranger = CustomUser.objects.create_user(
            username="other@example.com",
            email="other@example.com",
            password="pw-for-tests",
        )
        ProfessionalProfile.objects.get_or_create(user=stranger)

        self.client.force_login(stranger)
        response = self.client.get(
            "/professionals/health-program-invitations/my-interventions/"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["groups"], [])
