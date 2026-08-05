"""
Tests for the changes agreed in the 13 July 2026 client review:

  item d — short, org-prefixed, platform-unique participant IDs
  item e — gender / age / location on participant registration
  item g — participant / vitals / intervention sections
  item i — automatic BMI, blood pressure as free text
"""

from datetime import date

from django.test import TestCase, override_settings

from accounts.models import CustomUser
from .models import (
    HealthProgram,
    InterventionField,
    Organization,
    Participant,
    ProgramIntervention,
    ProgramInterventionType,
)
from .vitals import (
    blood_pressure_category,
    calculate_bmi,
    bmi_category,
    parse_blood_pressure,
    apply_derived_values,
)


def make_org(name, email):
    user = CustomUser.objects.create_user(
        username=email, email=email, password="pw-for-tests"
    )
    org, _ = Organization.objects.get_or_create(user=user)
    org.organization_name = name
    org.save()
    return org, user


class ParticipantCodeTests(TestCase):
    """Item d — 'SJ001' rather than a 36-character UUID."""

    def test_prefix_is_derived_from_organisation_initials(self):
        org, _ = make_org("St. Joana Foundation", "sj@example.com")
        # "St." is a stop-word, so the initials are J(oana) F(oundation).
        self.assertEqual(org.participant_code_prefix, "JF")

    def test_participant_codes_are_short_prefixed_and_unique(self):
        org, _ = make_org("Bright Care Trust", "bct@example.com")
        codes = [
            Participant.objects.create(
                organization=org, fullname=f"Person {i}"
            ).participant_code
            for i in range(3)
        ]
        prefix = org.participant_code_prefix

        for code in codes:
            # Short enough to read aloud and write on a slip.
            self.assertLessEqual(len(code), 7, code)
            self.assertTrue(code.startswith(prefix), code)
        self.assertEqual(len(set(codes)), 3)

    def test_the_whole_organisation_prefix_is_kept(self):
        """
        An organisation whose two-letter prefix was taken holds a three-letter
        one. Trimming the prefix to a fixed width here would print the same
        visible prefix on two different organisations' slips.
        """
        first, _ = make_org("Hope Health Trust", "hht-a@example.com")
        second, _ = make_org("Hope Health Trust", "hht-b@example.com")

        a = Participant.objects.create(organization=first, fullname="A")
        b = Participant.objects.create(organization=second, fullname="B")

        self.assertTrue(a.participant_code.startswith(first.participant_code_prefix))
        self.assertTrue(b.participant_code.startswith(second.participant_code_prefix))

    def test_codes_are_not_guessable_from_one_another(self):
        """
        The code is now the handle used to look a participant up, and the
        lookup returns their name, phone, age and location. Sequential codes
        would let anyone holding one slip enumerate every other participant.
        """
        org, _ = make_org("Bright Care Trust", "bct2@example.com")
        codes = [
            Participant.objects.create(
                organization=org, fullname=f"Person {i}"
            ).participant_code
            for i in range(8)
        ]

        tails = [code[2:] for code in codes]
        self.assertNotEqual(
            tails,
            sorted(tails),
            "Codes came out in ascending order — they are still enumerable.",
        )

    def test_codes_avoid_visually_ambiguous_characters(self):
        """Staff transcribe these by hand off paper slips."""
        org, _ = make_org("Bright Care Trust", "bct3@example.com")
        codes = [
            Participant.objects.create(
                organization=org, fullname=f"Person {i}"
            ).participant_code[2:]
            for i in range(25)
        ]
        for code in codes:
            self.assertFalse(
                set(code) & set("O0I1LS5Z2"),
                f"{code} contains a character that is misread on paper.",
            )

    def test_a_participant_without_an_organisation_still_gets_a_code(self):
        """
        The code used to be skipped when no organisation was set, leaving those
        rows with no identifier at all — unreachable once the phone number
        became optional.
        """
        participant = Participant.objects.create(fullname="Unattached")
        self.assertTrue(participant.participant_code)

    def test_prefixes_never_collide_across_organisations(self):
        """
        Two organisations with the same initials must not share a prefix, or
        their participant codes would clash platform-wide.
        """
        first, _ = make_org("Hope Health Initiative", "hhi1@example.com")
        second, _ = make_org("Hope Health Initiative", "hhi2@example.com")

        self.assertNotEqual(
            first.participant_code_prefix, second.participant_code_prefix
        )

        a = Participant.objects.create(organization=first, fullname="A")
        b = Participant.objects.create(organization=second, fullname="B")
        self.assertNotEqual(a.participant_code, b.participant_code)

    def test_code_is_stable_once_assigned(self):
        org, _ = make_org("Kumasi Wellness Group", "kwg@example.com")
        p = Participant.objects.create(organization=org, fullname="Ama")
        original = p.participant_code

        p.fullname = "Ama Mensah"
        p.save()
        p.refresh_from_db()
        self.assertEqual(p.participant_code, original)


class ParticipantDemographicsTests(TestCase):
    """Item e — gender, age and location are part of standard registration."""

    def setUp(self):
        self.org, self.user = make_org("Accra Outreach", "ao@example.com")

    def test_demographics_are_stored(self):
        p = Participant.objects.create(
            organization=self.org,
            fullname="Kofi Mensah",
            gender=Participant.Gender.MALE,
            age=34,
            location="Tse-Addo, Accra",
        )
        p.refresh_from_db()
        self.assertEqual(p.gender, "male")
        self.assertEqual(p.current_age, 34)
        self.assertEqual(p.location, "Tse-Addo, Accra")

    def test_date_of_birth_takes_precedence_over_stated_age(self):
        """A recorded DOB stays accurate as years pass; a stated age does not."""
        p = Participant.objects.create(
            organization=self.org,
            fullname="Akua",
            date_of_birth=date(1990, 1, 1),
            age=12,  # stale or mistyped
        )
        expected = date.today().year - 1990
        if (date.today().month, date.today().day) < (1, 1):
            expected -= 1
        self.assertEqual(p.current_age, expected)


class InterventionSectionTests(TestCase):
    """Item g — three sections; item i — BMI computed, BP free text."""

    def setUp(self):
        self.org, self.user = make_org("Section Test Org", "sto@example.com")
        self.program = HealthProgram.objects.create(
            organization=self.org,
            program_name="Screening Day",
            start_date=date.today(),
            target_participants=100,
            created_by=self.user,
        )
        itype = ProgramInterventionType.objects.create(name="General Screening")
        self.intervention = ProgramIntervention.objects.create(
            intervention_type=itype, program=self.program
        )

    def test_fields_default_to_the_intervention_section(self):
        field = InterventionField.objects.create(
            intervention=self.intervention, name="Referred?"
        )
        self.assertEqual(field.section, InterventionField.Section.INTERVENTION)

    def test_bmi_field_is_always_computed(self):
        """Even if a client asks for an editable BMI field, it is derived."""
        field = InterventionField.objects.create(
            intervention=self.intervention,
            name="BMI",
            section=InterventionField.Section.VITALS,
            field_key=InterventionField.FieldKey.BMI,
            is_computed=False,
        )
        field.refresh_from_db()
        self.assertTrue(field.is_computed)

    def test_blood_pressure_is_forced_to_text(self):
        """So "120/80" can be entered exactly as measured."""
        field = InterventionField.objects.create(
            intervention=self.intervention,
            name="Blood Pressure",
            section=InterventionField.Section.VITALS,
            field_key=InterventionField.FieldKey.BLOOD_PRESSURE,
            field_type=InterventionField.FieldType.NUMBER,
        )
        field.refresh_from_db()
        self.assertEqual(field.field_type, InterventionField.FieldType.TEXT)

    def test_fields_are_ordered_by_section_then_order(self):
        InterventionField.objects.create(
            intervention=self.intervention,
            name="Diagnosis",
            section=InterventionField.Section.INTERVENTION,
            order=0,
        )
        InterventionField.objects.create(
            intervention=self.intervention,
            name="Weight",
            section=InterventionField.Section.VITALS,
            order=0,
        )
        InterventionField.objects.create(
            intervention=self.intervention,
            name="Occupation",
            section=InterventionField.Section.PARTICIPANT,
            order=0,
        )
        names = list(
            InterventionField.objects.filter(
                intervention=self.intervention
            ).values_list("name", flat=True)
        )
        # Alphabetical section codes happen to order INTERVENTION < PARTICIPANT
        # < VITALS; what matters is that fields group by section.
        sections = list(
            InterventionField.objects.filter(
                intervention=self.intervention
            ).values_list("section", flat=True)
        )
        self.assertEqual(sections, sorted(sections))
        self.assertEqual(len(names), 3)


class BMITests(TestCase):
    """Item i — automatic BMI from height and weight."""

    def test_bmi_is_calculated_correctly(self):
        # 70 kg at 170 cm → 70 / 1.7² = 24.2
        self.assertEqual(calculate_bmi(170, 70), 24.2)

    def test_bmi_accepts_string_input_from_form_fields(self):
        self.assertEqual(calculate_bmi("170", "70"), 24.2)

    def test_bmi_is_none_when_a_measurement_is_missing(self):
        self.assertIsNone(calculate_bmi(170, None))
        self.assertIsNone(calculate_bmi(None, 70))
        self.assertIsNone(calculate_bmi("", ""))

    def test_bmi_rejects_implausible_measurements(self):
        """Height in metres instead of centimetres must not yield a BMI."""
        self.assertIsNone(calculate_bmi(1.7, 70))
        self.assertIsNone(calculate_bmi(170, 900))

    def test_bmi_categories(self):
        self.assertEqual(bmi_category(17.0), "Underweight")
        self.assertEqual(bmi_category(22.0), "Normal")
        self.assertEqual(bmi_category(27.0), "Overweight")
        self.assertEqual(bmi_category(33.0), "Obese")

    def test_derived_values_produce_bmi_from_tagged_fields(self):
        derived = apply_derived_values({"height": "170", "weight": "70"})
        self.assertEqual(derived, {"bmi": "24.2"})

    def test_derived_values_empty_without_both_measurements(self):
        self.assertEqual(apply_derived_values({"height": "170"}), {})


class BloodPressureTests(TestCase):
    """Item i — BP entered as "120/80" text but still machine-readable."""

    def test_standard_reading_parses(self):
        self.assertEqual(parse_blood_pressure("120/80"), (120, 80))

    def test_spacing_and_separators_are_tolerated(self):
        self.assertEqual(parse_blood_pressure(" 120 / 80 "), (120, 80))
        self.assertEqual(parse_blood_pressure("120-80"), (120, 80))

    def test_unparseable_text_is_not_rejected_just_unparsed(self):
        self.assertEqual(parse_blood_pressure("not taken"), (None, None))
        self.assertEqual(parse_blood_pressure(""), (None, None))

    def test_transposed_reading_is_not_silently_corrected(self):
        self.assertEqual(parse_blood_pressure("80/120"), (None, None))

    def test_categories(self):
        self.assertEqual(blood_pressure_category("110/70"), "Normal")
        self.assertEqual(blood_pressure_category("125/75"), "Elevated")
        self.assertEqual(blood_pressure_category("135/85"), "Hypertension Stage 1")
        self.assertEqual(blood_pressure_category("150/95"), "Hypertension Stage 2")
        self.assertEqual(blood_pressure_category("190/125"), "Hypertensive Crisis")
        self.assertIsNone(blood_pressure_category("not taken"))


class VolunteerEligibilityTests(TestCase):
    """Item n — volunteer roles are not limited to health professionals."""

    def setUp(self):
        self.org, self.owner = make_org("Volunteer Org", "vo@example.com")

    def _job(self, job_type="volunteering", open_to_all=False):
        from .models import LocumJob

        return LocumJob.objects.create(
            title=f"Role {job_type}-{open_to_all}",
            organization=self.org,
            description="Help out at the screening event.",
            location="Accra",
            job_type=job_type,
            open_to_non_professionals=open_to_all,
            is_active=True,
            approved=True,
        )

    def test_open_volunteer_role_accepts_non_professionals(self):
        job = self._job(open_to_all=True)
        self.assertTrue(job.accepts_non_professionals)

    def test_closed_volunteer_role_still_restricted(self):
        job = self._job(open_to_all=False)
        self.assertFalse(job.accepts_non_professionals)

    def test_paid_role_never_open_to_non_professionals(self):
        """Ticking the flag on a paid role must not open it up."""
        job = self._job(job_type="paid", open_to_all=True)
        self.assertFalse(job.accepts_non_professionals)


class StaffRoleTests(TestCase):
    """Item l — volunteers assist with data entry, never shown as clinicians."""

    def setUp(self):
        self.org, _ = make_org("Staff Org", "so@example.com")

    def _staff(self, **kwargs):
        from .models import Staff

        defaults = dict(
            organization=self.org,
            first_name="Ama",
            last_name="Owusu",
            email="ama@example.com",
        )
        defaults.update(kwargs)
        return Staff.objects.create(**defaults)

    def test_members_are_non_clinical_by_default(self):
        staff = self._staff()
        self.assertFalse(staff.is_clinical)

    def test_non_clinical_role_is_labelled_as_support(self):
        staff = self._staff(role="Data Entry")
        self.assertIn("Volunteer / Support", staff.display_role)

    def test_clinical_role_is_shown_plainly(self):
        staff = self._staff(role="Nurse", is_clinical=True)
        self.assertEqual(staff.display_role, "Nurse")

    def test_maker_can_record_but_not_approve(self):
        from .models import Staff

        staff = self._staff(account_type=Staff.AccountType.MAKER)
        self.assertTrue(staff.has_permission("record_participants"))
        self.assertFalse(staff.has_permission("approve_records"))

    def test_revoked_member_has_no_permissions(self):
        from .models import Staff

        staff = self._staff(
            account_type=Staff.AccountType.CHECKER, status=Staff.Status.REVOKED
        )
        self.assertFalse(staff.has_permission("record_participants"))

    def test_explicit_permissions_override_defaults(self):
        from .models import Staff

        staff = self._staff(
            account_type=Staff.AccountType.CHECKER, permissions=["view_reports"]
        )
        self.assertTrue(staff.has_permission("view_reports"))
        self.assertFalse(staff.has_permission("approve_records"))


class PaperWorkflowTests(TestCase):
    """Item k — the platform must fit paper-first outreach operations."""

    def setUp(self):
        self.org, self.user = make_org("Paper Org", "po@example.com")
        self.program = HealthProgram.objects.create(
            organization=self.org,
            program_name="Outreach Day",
            start_date=date.today(),
            target_participants=100,
            created_by=self.user,
        )
        itype = ProgramInterventionType.objects.create(name="Screening")
        self.intervention = ProgramIntervention.objects.create(
            intervention_type=itype, program=self.program
        )

    def test_blank_queue_slips_get_distinct_codes(self):
        slips = [
            Participant.objects.create(organization=self.org, fullname="")
            for _ in range(3)
        ]
        codes = [s.participant_code for s in slips]
        prefix = self.org.participant_code_prefix

        self.assertEqual(len(set(codes)), 3)
        for code in codes:
            self.assertTrue(code.startswith(prefix), code)

    def test_recorded_at_defaults_to_entry_time(self):
        from .models import InterventionResponse

        participant = Participant.objects.create(
            organization=self.org, fullname="Kojo"
        )
        response = InterventionResponse.objects.create(
            intervention=self.intervention, participant=participant
        )
        self.assertIsNotNone(response.recorded_at)
        self.assertEqual(response.recorded_at, response.date_created)

    def test_transcribed_record_keeps_the_collection_time(self):
        """
        A slip typed up in the evening must report against the event date, not
        the transcription date, or post-event reporting is wrong.
        """
        from datetime import timedelta

        from django.utils import timezone

        from .models import InterventionResponse

        collected = timezone.now() - timedelta(days=2)
        participant = Participant.objects.create(organization=self.org, fullname="Esi")
        response = InterventionResponse.objects.create(
            intervention=self.intervention,
            participant=participant,
            recorded_at=collected,
            entry_mode="transcribed",
        )
        self.assertEqual(response.recorded_at, collected)
        self.assertNotEqual(response.recorded_at, response.date_created)
        self.assertEqual(response.entry_mode, "transcribed")


class InterventionTemplateTests(TestCase):
    """Item h — preset templates that organisers can apply then modify."""

    def setUp(self):
        self.org, self.user = make_org("Template Org", "to@example.com")

    def test_seeded_platform_templates_are_available(self):
        from django.core.management import call_command

        from .models import InterventionTemplate

        call_command("seed_intervention_templates", verbosity=0)
        templates = InterventionTemplate.objects.filter(is_platform_default=True)
        self.assertGreaterEqual(templates.count(), 5)

        general = templates.get(name="General Health Screening")
        self.assertGreater(general.fields.count(), 0)

    def test_seeded_bmi_field_is_computed_and_bp_is_text(self):
        from django.core.management import call_command

        from .models import InterventionTemplate

        call_command("seed_intervention_templates", verbosity=0)
        general = InterventionTemplate.objects.get(name="General Health Screening")

        bmi = general.fields.get(field_key=InterventionField.FieldKey.BMI)
        self.assertTrue(bmi.is_computed)

        bp = general.fields.get(field_key=InterventionField.FieldKey.BLOOD_PRESSURE)
        self.assertEqual(bp.field_type, InterventionField.FieldType.TEXT)

    def test_seeding_is_idempotent(self):
        from django.core.management import call_command

        from .models import InterventionTemplate

        call_command("seed_intervention_templates", verbosity=0)
        first = InterventionTemplate.objects.filter(is_platform_default=True).count()
        call_command("seed_intervention_templates", verbosity=0)
        second = InterventionTemplate.objects.filter(is_platform_default=True).count()
        self.assertEqual(first, second)


class OfflineSyncTests(TestCase):
    """
    Item b — hybrid offline capture with automatic synchronisation.

    The two properties that matter: a replayed queue item must not duplicate,
    and two people recording the same participant must converge on one record
    without the older reading overwriting the newer one.
    """

    def setUp(self):
        from .models import InterventionField

        self.org, self.user = make_org("Sync Org", "sync@example.com")
        self.other_user = CustomUser.objects.create_user(
            username="nurse@example.com",
            email="nurse@example.com",
            password="pw-for-tests",
        )
        self.program = HealthProgram.objects.create(
            organization=self.org,
            program_name="Offline Day",
            start_date=date.today(),
            target_participants=100,
            created_by=self.user,
        )
        itype = ProgramInterventionType.objects.create(name="Screening")
        self.intervention = ProgramIntervention.objects.create(
            intervention_type=itype, program=self.program
        )
        self.height = InterventionField.objects.create(
            intervention=self.intervention,
            name="Height (cm)",
            field_type=InterventionField.FieldType.NUMBER,
            section=InterventionField.Section.VITALS,
            field_key=InterventionField.FieldKey.HEIGHT,
        )
        self.weight = InterventionField.objects.create(
            intervention=self.intervention,
            name="Weight (kg)",
            field_type=InterventionField.FieldType.NUMBER,
            section=InterventionField.Section.VITALS,
            field_key=InterventionField.FieldKey.WEIGHT,
        )
        self.bmi = InterventionField.objects.create(
            intervention=self.intervention,
            name="BMI",
            field_type=InterventionField.FieldType.NUMBER,
            section=InterventionField.Section.VITALS,
            field_key=InterventionField.FieldKey.BMI,
        )
        self.notes = InterventionField.objects.create(
            intervention=self.intervention,
            name="Notes",
            field_type=InterventionField.FieldType.TEXT,
            section=InterventionField.Section.INTERVENTION,
        )

    def _item(self, client_uuid, answers, recorded_at=None, phone="+233200000001"):
        from django.utils import timezone

        return {
            "client_uuid": client_uuid,
            "intervention": str(self.intervention.id),
            "participant": {"phone_number": phone, "fullname": "Kofi"},
            "answers": answers,
            "recorded_at": recorded_at or timezone.now(),
        }

    def test_queued_record_is_applied(self):
        from .models import InterventionResponse
        from .sync import sync_batch

        outcomes = sync_batch(
            self.org,
            [
                self._item(
                    "11111111-1111-1111-1111-111111111111",
                    [
                        {"field": str(self.height.id), "value": "170"},
                        {"field": str(self.weight.id), "value": "70"},
                    ],
                )
            ],
            self.user,
        )
        self.assertEqual(outcomes[0].status, "created")
        self.assertEqual(InterventionResponse.objects.count(), 1)

    def test_replaying_the_same_item_does_not_duplicate(self):
        """
        A timed-out request has usually still been applied, so the client
        retries the same item. That must be a no-op, not a second record.
        """
        from .models import InterventionResponse
        from .sync import sync_batch

        item = self._item(
            "22222222-2222-2222-2222-222222222222",
            [{"field": str(self.height.id), "value": "165"}],
        )
        first = sync_batch(self.org, [item], self.user)
        second = sync_batch(self.org, [item], self.user)

        self.assertEqual(first[0].status, "created")
        self.assertEqual(second[0].status, "duplicate")
        self.assertEqual(InterventionResponse.objects.count(), 1)
        self.assertEqual(first[0].response_id, second[0].response_id)

    def test_two_devices_merge_into_one_record(self):
        """
        A nurse records vitals, a doctor adds notes — both offline. They must
        converge on one record for the participant, not two conflicting ones.
        """
        from .models import InterventionResponse, InterventionResponseValue
        from .sync import sync_batch

        sync_batch(
            self.org,
            [
                self._item(
                    "33333333-3333-3333-3333-333333333333",
                    [{"field": str(self.height.id), "value": "170"}],
                )
            ],
            self.other_user,
        )
        outcomes = sync_batch(
            self.org,
            [
                self._item(
                    "44444444-4444-4444-4444-444444444444",
                    [{"field": str(self.notes.id), "value": "Referred to clinic"}],
                )
            ],
            self.user,
        )

        self.assertEqual(outcomes[0].status, "merged")
        self.assertEqual(InterventionResponse.objects.count(), 1)

        response = InterventionResponse.objects.get()
        values = {
            v.field.name: v.value
            for v in InterventionResponseValue.objects.filter(response=response)
        }
        self.assertEqual(values["Height (cm)"], "170")
        self.assertEqual(values["Notes"], "Referred to clinic")

    def test_a_stale_offline_value_does_not_overwrite_a_newer_one(self):
        """
        A device that was offline for hours must not clobber a correction made
        later. The older reading is kept out and reported as a conflict.
        """
        from datetime import timedelta

        from django.utils import timezone

        from .models import InterventionResponseValue
        from .sync import sync_batch

        now = timezone.now()

        # The doctor's later correction syncs first.
        sync_batch(
            self.org,
            [
                self._item(
                    "55555555-5555-5555-5555-555555555555",
                    [{"field": str(self.weight.id), "value": "72"}],
                    recorded_at=now,
                )
            ],
            self.user,
        )

        # The nurse's earlier reading arrives afterwards from a stale queue.
        outcomes = sync_batch(
            self.org,
            [
                self._item(
                    "66666666-6666-6666-6666-666666666666",
                    [{"field": str(self.weight.id), "value": "68"}],
                    recorded_at=now - timedelta(hours=3),
                )
            ],
            self.other_user,
        )

        stored = InterventionResponseValue.objects.get(field=self.weight)
        self.assertEqual(stored.value, "72", "the newer reading must survive")

        conflicts = outcomes[0].conflicts
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["kept_value"], "72")
        self.assertEqual(conflicts[0]["rejected_value"], "68")

    def test_bmi_is_derived_on_sync(self):
        from .models import InterventionResponseValue
        from .sync import sync_batch

        sync_batch(
            self.org,
            [
                self._item(
                    "77777777-7777-7777-7777-777777777777",
                    [
                        {"field": str(self.height.id), "value": "170"},
                        {"field": str(self.weight.id), "value": "70"},
                    ],
                )
            ],
            self.user,
        )
        bmi_value = InterventionResponseValue.objects.get(field=self.bmi)
        self.assertEqual(bmi_value.value, "24.2")

    def test_one_bad_item_does_not_block_the_rest(self):
        from .models import InterventionResponse
        from .sync import sync_batch

        outcomes = sync_batch(
            self.org,
            [
                {"client_uuid": "", "intervention": str(self.intervention.id)},
                self._item(
                    "88888888-8888-8888-8888-888888888888",
                    [{"field": str(self.height.id), "value": "160"}],
                    phone="+233200000009",
                ),
            ],
            self.user,
        )
        self.assertEqual(outcomes[0].status, "failed")
        self.assertEqual(outcomes[1].status, "created")
        self.assertEqual(InterventionResponse.objects.count(), 1)

    def test_unknown_intervention_is_rejected_not_crashed(self):
        from .sync import sync_batch

        item = self._item(
            "99999999-9999-9999-9999-999999999999",
            [],
        )
        item["intervention"] = "00000000-0000-0000-0000-000000000000"
        outcomes = sync_batch(self.org, [item], self.user)
        self.assertEqual(outcomes[0].status, "failed")


class DataEntryPermissionTests(TestCase):
    """
    An invited health professional is not a member of the organisation, but is
    exactly who records data at an outreach event. Membership-only gating would
    lock them out of sync, lookup and participant history (items b, c and f).
    """

    def setUp(self):
        from .models import HealthProgramInvitation

        self.org, self.owner = make_org("Perm Org", "perm@example.com")
        self.program = HealthProgram.objects.create(
            organization=self.org,
            program_name="Perm Day",
            start_date=date.today(),
            target_participants=50,
            created_by=self.owner,
        )
        self.doctor = CustomUser.objects.create_user(
            username="doc@example.com",
            email="doc@example.com",
            password="pw-for-tests",
        )
        self.stranger = CustomUser.objects.create_user(
            username="stranger@example.com",
            email="stranger@example.com",
            password="pw-for-tests",
        )
        HealthProgramInvitation.objects.create(
            program=self.program,
            invited_by=self.org,
            invited_to=self.doctor,
            status=HealthProgramInvitation.InvitationStatus.ACCEPTED,
        )

    def _check(self, user):
        from .permissions import OrganizationDataEntryAllowed

        class FakeView:
            kwargs = {"organization_id": str(self.org.id)}

        class FakeRequest:
            pass

        request = FakeRequest()
        request.user = user
        return OrganizationDataEntryAllowed().has_permission(request, FakeView())

    def test_owner_is_allowed(self):
        self.assertTrue(self._check(self.owner))

    def test_invited_professional_is_allowed(self):
        self.assertTrue(self._check(self.doctor))

    def test_unrelated_user_is_denied(self):
        self.assertFalse(self._check(self.stranger))

    def test_pending_invitation_is_not_enough(self):
        from .models import HealthProgramInvitation

        HealthProgramInvitation.objects.filter(invited_to=self.doctor).update(
            status=HealthProgramInvitation.InvitationStatus.PENDING
        )
        self.assertFalse(self._check(self.doctor))


class PhoneOptionalParticipantTests(TestCase):
    """
    The phone number is no longer required to register a participant.

    Outreach attendees frequently have no phone or decline to give one, and a
    mandatory field that cannot be filled gets worked around with junk data.
    The auto-assigned participant code carries identity instead, so these tests
    pin down that a record without a phone number is still findable and that
    two such records do not collapse into the same person.
    """

    def setUp(self):
        self.org, self.user = make_org("No Phone Org", "nophone@example.com")
        self.program = HealthProgram.objects.create(
            organization=self.org,
            program_name="Screening Day",
            start_date=date.today(),
            target_participants=50,
            created_by=self.user,
        )
        itype = ProgramInterventionType.objects.create(name="Vitals")
        self.intervention = ProgramIntervention.objects.create(
            intervention_type=itype, program=self.program
        )
        self.notes = InterventionField.objects.create(
            intervention=self.intervention,
            name="Notes",
            field_type=InterventionField.FieldType.TEXT,
            section=InterventionField.Section.INTERVENTION,
        )

    def _sync(self, client_uuid, participant):
        from .sync import sync_batch

        return sync_batch(
            self.org,
            [
                {
                    "client_uuid": client_uuid,
                    "intervention": str(self.intervention.id),
                    "participant": participant,
                    "answers": [{"field": str(self.notes.id), "value": "seen"}],
                }
            ],
            self.user,
        )[0]

    def test_serializer_accepts_a_participant_with_no_phone_number(self):
        from .serializers import ParticipantSerializer

        serializer = ParticipantSerializer(data={"fullname": "Adwoa"})
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_record_without_a_phone_number_is_created_and_coded(self):
        outcome = self._sync(
            "aaaaaaaa-0000-0000-0000-000000000001", {"fullname": "Adwoa"}
        )
        self.assertEqual(outcome.status, "created")
        self.assertTrue(outcome.participant_code)

    def test_two_participants_without_phones_stay_separate(self):
        """
        The regression this guards: a blank phone number used to be sent as
        the bare dialling code, so every participant who skipped the field
        matched the same record and overwrote each other's vitals.
        """
        first = self._sync(
            "aaaaaaaa-0000-0000-0000-000000000002", {"fullname": "Adwoa"}
        )
        second = self._sync(
            "aaaaaaaa-0000-0000-0000-000000000003", {"fullname": "Yaw"}
        )

        self.assertNotEqual(first.participant_code, second.participant_code)
        self.assertEqual(Participant.objects.filter(organization=self.org).count(), 2)

    def test_a_returning_participant_is_matched_on_their_code(self):
        """The paper-slip flow when the device is offline and cannot look up."""
        first = self._sync(
            "aaaaaaaa-0000-0000-0000-000000000004", {"fullname": "Kwesi"}
        )
        code = first.participant_code

        second = self._sync(
            "aaaaaaaa-0000-0000-0000-000000000005",
            {"participant_code": code, "location": "Nsawam"},
        )

        self.assertEqual(second.participant_code, code)
        self.assertEqual(Participant.objects.filter(organization=self.org).count(), 1)
        participant = Participant.objects.get(participant_code=code)
        # The later record must not blank out what was captured earlier.
        self.assertEqual(participant.fullname, "Kwesi")
        self.assertEqual(participant.location, "Nsawam")

    def test_a_code_from_another_organisation_does_not_match(self):
        other_org, _ = make_org("Other Org", "otherorg@example.com")
        theirs = Participant.objects.create(organization=other_org, fullname="Theirs")

        outcome = self._sync(
            "aaaaaaaa-0000-0000-0000-000000000006",
            {"participant_code": theirs.participant_code, "fullname": "Mine"},
        )

        self.assertNotEqual(outcome.participant_code, theirs.participant_code)
        theirs.refresh_from_db()
        self.assertEqual(theirs.fullname, "Theirs")


class SyncTimestampCoercionTests(TestCase):
    """
    The sync endpoint reads `request.data` directly rather than through a
    serializer, so `recorded_at` arrives as the ISO string JSON carries it as.

    Comparing that string against a stored datetime raised
    "'<' not supported between instances of 'str' and 'datetime.datetime'".
    It only bit on the *second* submission for a participant — the first has
    nothing to merge with and never reaches the comparison — so the record sat
    in the offline queue retrying forever.
    """

    def setUp(self):
        self.org, self.user = make_org("Timestamp Org", "ts@example.com")
        self.program = HealthProgram.objects.create(
            organization=self.org,
            program_name="Screening",
            start_date=date.today(),
            target_participants=10,
            created_by=self.user,
        )
        itype = ProgramInterventionType.objects.create(name="Vitals")
        self.intervention = ProgramIntervention.objects.create(
            intervention_type=itype, program=self.program
        )
        self.height = InterventionField.objects.create(
            intervention=self.intervention,
            name="Height (cm)",
            field_type=InterventionField.FieldType.NUMBER,
            section=InterventionField.Section.VITALS,
            field_key=InterventionField.FieldKey.HEIGHT,
        )

    def _item(self, client_uuid, value, recorded_at):
        return {
            "client_uuid": client_uuid,
            "intervention": str(self.intervention.id),
            "participant": {"fullname": "Kofi", "phone_number": "+233240000001"},
            "answers": [{"field": str(self.height.id), "value": value}],
            "recorded_at": recorded_at,
        }

    def test_iso_string_timestamps_survive_a_merge(self):
        """The exact shape the browser sends: `new Date().toISOString()`."""
        from django.utils import timezone
        from datetime import timedelta

        from .sync import sync_batch

        earlier = (timezone.now() - timedelta(hours=2)).isoformat()
        later = timezone.now().isoformat()

        first = sync_batch(self.org, [self._item("cccccccc-0000-0000-0000-000000000001", "170", earlier)], self.user)
        # The merge path is where the comparison lives.
        second = sync_batch(self.org, [self._item("cccccccc-0000-0000-0000-000000000002", "172", later)], self.user)

        self.assertEqual(first[0].status, "created")
        self.assertEqual(second[0].status, "merged", second[0].detail)

    def test_a_stale_queued_reading_still_loses_to_a_newer_one(self):
        """
        Coercion must not quietly break last-write-wins: a reading captured
        earlier but synced later must not overwrite the newer correction.
        """
        from django.utils import timezone
        from datetime import timedelta

        from .models import InterventionResponseValue
        from .sync import sync_batch

        newer = timezone.now().isoformat()
        older = (timezone.now() - timedelta(hours=3)).isoformat()

        sync_batch(self.org, [self._item("cccccccc-0000-0000-0000-000000000003", "172", newer)], self.user)
        outcome = sync_batch(self.org, [self._item("cccccccc-0000-0000-0000-000000000004", "160", older)], self.user)

        stored = InterventionResponseValue.objects.get(field=self.height)
        self.assertEqual(stored.value, "172")
        self.assertTrue(outcome[0].conflicts)

    def test_an_unparseable_timestamp_falls_back_to_now(self):
        """A record with an odd clock beats a record rejected at an event."""
        from .sync import sync_batch

        outcome = sync_batch(self.org, [self._item("cccccccc-0000-0000-0000-000000000005", "168", "not-a-date")], self.user)
        self.assertEqual(outcome[0].status, "created", outcome[0].detail)

    def test_a_missing_timestamp_still_works(self):
        from .sync import sync_batch

        item = self._item("cccccccc-0000-0000-0000-000000000006", "165", None)
        del item["recorded_at"]
        outcome = sync_batch(self.org, [item], self.user)
        self.assertEqual(outcome[0].status, "created", outcome[0].detail)


class InterventionTitleTests(TestCase):
    """
    Item h — an intervention carries the organiser's own title.

    The type alone is too coarse: one programme routinely runs several
    interventions of the same type ("Screening" on day 1 and day 2, adults and
    children), and they were indistinguishable in every list.
    """

    def setUp(self):
        self.org, self.user = make_org("Title Org", "title@example.com")
        self.program = HealthProgram.objects.create(
            organization=self.org,
            program_name="Outreach Week",
            start_date=date.today(),
            target_participants=10,
            created_by=self.user,
        )
        self.itype = ProgramInterventionType.objects.create(name="Eye Screening")

    def test_a_title_is_used_when_set(self):
        intervention = ProgramIntervention.objects.create(
            intervention_type=self.itype,
            program=self.program,
            title="Day 1 — Adults",
        )
        self.assertEqual(intervention.display_title, "Day 1 — Adults")

    def test_it_falls_back_to_the_type_name(self):
        """Existing interventions have no title and must still read sensibly."""
        intervention = ProgramIntervention.objects.create(
            intervention_type=self.itype, program=self.program
        )
        self.assertEqual(intervention.display_title, "Eye Screening")

    def test_a_whitespace_only_title_falls_back_too(self):
        intervention = ProgramIntervention.objects.create(
            intervention_type=self.itype, program=self.program, title="   "
        )
        self.assertEqual(intervention.display_title, "Eye Screening")

    def test_two_interventions_of_one_type_are_distinguishable(self):
        """The whole point of the field."""
        first = ProgramIntervention.objects.create(
            intervention_type=self.itype, program=self.program, title="Day 1 — Adults"
        )
        second = ProgramIntervention.objects.create(
            intervention_type=self.itype,
            program=self.program,
            title="Day 2 — Children",
        )
        self.assertNotEqual(first.display_title, second.display_title)

    def test_the_serializer_exposes_the_title_and_the_display_name(self):
        from .serializers import ProgramInterventionSerializer

        intervention = ProgramIntervention.objects.create(
            intervention_type=self.itype, program=self.program, title="Day 1"
        )
        data = ProgramInterventionSerializer(intervention).data
        self.assertEqual(data["title"], "Day 1")
        self.assertEqual(data["display_title"], "Day 1")
        # The type is still reported separately — it drives reporting.
        self.assertEqual(data["intervention_type_name"], "Eye Screening")

    def test_a_response_is_named_by_the_title(self):
        from .models import InterventionResponse
        from .serializers import InterventionResponseSerializer

        intervention = ProgramIntervention.objects.create(
            intervention_type=self.itype, program=self.program, title="Day 2 — Children"
        )
        participant = Participant.objects.create(organization=self.org, fullname="Ama")
        response = InterventionResponse.objects.create(
            intervention=intervention, participant=participant
        )
        data = InterventionResponseSerializer(response).data
        self.assertEqual(data["intervention_name"], "Day 2 — Children")

    def test_clearing_a_title_restores_the_type_name(self):
        """
        Update keys on presence, not truthiness — a deliberately cleared title
        must fall back rather than be silently ignored.
        """
        intervention = ProgramIntervention.objects.create(
            intervention_type=self.itype, program=self.program, title="Temporary"
        )
        intervention.title = ""
        intervention.save()
        intervention.refresh_from_db()
        self.assertEqual(intervention.display_title, "Eye Screening")


class ParticipantCrossInterventionTests(TestCase):
    """
    Data linking — a participant's records must be reachable from any one of
    them.

    Lookup by code or phone already surfaced earlier records *at data-entry
    time*, but once a response was saved the link disappeared: viewing a record
    in intervention A gave no indication the same person also had one in B.
    """

    def setUp(self):
        self.org, self.user = make_org("Linking Org", "linking@example.com")
        self.program = HealthProgram.objects.create(
            organization=self.org,
            program_name="Health Day",
            start_date=date.today(),
            target_participants=10,
            created_by=self.user,
        )
        itype = ProgramInterventionType.objects.create(name="Screening")
        self.a = ProgramIntervention.objects.create(
            intervention_type=itype, program=self.program, title="Intervention A"
        )
        self.b = ProgramIntervention.objects.create(
            intervention_type=itype, program=self.program, title="Intervention B"
        )
        self.field_a = InterventionField.objects.create(
            intervention=self.a, name="Visual acuity"
        )
        self.field_b = InterventionField.objects.create(
            intervention=self.b, name="Blood sugar"
        )
        self.participant = Participant.objects.create(
            organization=self.org, fullname="Kofi"
        )

    def _record(self, intervention, field, value):
        from .models import InterventionResponse, InterventionResponseValue

        response = InterventionResponse.objects.create(
            intervention=intervention, participant=self.participant
        )
        InterventionResponseValue.objects.create(
            response=response, field=field, value=value
        )
        return response

    def _history(self):
        self.client.force_login(self.user)
        url = (
            f"/communities/{self.org.id}/participants/{self.participant.id}/history/"
        )
        return self.client.get(url)

    def test_a_record_in_b_is_visible_from_the_history(self):
        self._record(self.a, self.field_a, "6/6")
        self._record(self.b, self.field_b, "5.4")

        response = self._history()
        self.assertEqual(response.status_code, 200)

        names = {entry["intervention_name"] for entry in response.json()["history"]}
        self.assertEqual(names, {"Intervention A", "Intervention B"})

    def test_the_values_come_through_not_just_the_names(self):
        """A reviewer needs the reading, not merely that a record exists."""
        self._record(self.a, self.field_a, "6/6")
        self._record(self.b, self.field_b, "5.4")

        entries = self._history().json()["history"]
        by_name = {e["intervention_name"]: e for e in entries}
        values = {v["name"]: v["value"] for v in by_name["Intervention B"]["values"]}
        self.assertEqual(values, {"Blood sugar": "5.4"})

    def test_another_organisations_records_are_not_exposed(self):
        """Linking must not reach across organisations."""
        other_org, _ = make_org("Elsewhere", "elsewhere@example.com")
        other_program = HealthProgram.objects.create(
            organization=other_org,
            program_name="Their Day",
            start_date=date.today(),
            target_participants=5,
            created_by=self.user,
        )
        other_type = ProgramInterventionType.objects.create(name="Theirs")
        other_intervention = ProgramIntervention.objects.create(
            intervention_type=other_type, program=other_program, title="Their Record"
        )
        self._record(self.a, self.field_a, "6/6")
        self._record(other_intervention, self.field_a, "secret")

        names = {e["intervention_name"] for e in self._history().json()["history"]}
        self.assertNotIn("Their Record", names)

    def test_a_participant_with_one_record_reports_only_that_one(self):
        self._record(self.a, self.field_a, "6/6")
        entries = self._history().json()["history"]
        self.assertEqual(len(entries), 1)

    def test_the_response_payload_carries_the_participant_id(self):
        """
        Without it the client has no handle to fetch the history with, which
        is what kept the records unlinked in the first place.
        """
        from .serializers import InterventionResponseSerializer

        response = self._record(self.a, self.field_a, "6/6")
        data = InterventionResponseSerializer(response).data
        self.assertEqual(str(data["participant"]["id"]), str(self.participant.id))
        self.assertEqual(
            data["participant"]["participant_code"], self.participant.participant_code
        )


class ResponseListParticipantCodeTests(TestCase):
    """
    The responses table shows the participant code, so the list endpoint has
    to carry it — not just the detail view.
    """

    def setUp(self):
        self.org, self.user = make_org("Code Column Org", "codecol@example.com")
        self.program = HealthProgram.objects.create(
            organization=self.org,
            program_name="Screening",
            start_date=date.today(),
            target_participants=10,
            created_by=self.user,
        )
        itype = ProgramInterventionType.objects.create(name="Vitals")
        self.intervention = ProgramIntervention.objects.create(
            intervention_type=itype, program=self.program
        )
        self.participant = Participant.objects.create(
            organization=self.org, fullname="Ama"
        )

    def test_the_list_endpoint_returns_the_participant_code(self):
        from .models import InterventionResponse

        InterventionResponse.objects.create(
            intervention=self.intervention, participant=self.participant
        )
        self.client.force_login(self.user)
        url = (
            f"/communities/{self.org.id}/interventions/"
            f"{self.intervention.id}/responses/"
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, response.content[:300])

        payload = response.json()
        rows = payload.get("results", payload)
        self.assertTrue(rows, "no responses returned")
        self.assertEqual(
            rows[0]["participant"]["participant_code"],
            self.participant.participant_code,
        )

    def test_responses_are_searchable_by_participant_code(self):
        """The column is only useful if the search box accepts what it shows."""
        from .models import InterventionResponse

        other = Participant.objects.create(organization=self.org, fullname="Kofi")
        InterventionResponse.objects.create(
            intervention=self.intervention, participant=self.participant
        )
        InterventionResponse.objects.create(
            intervention=self.intervention, participant=other
        )

        self.client.force_login(self.user)
        url = (
            f"/communities/{self.org.id}/interventions/"
            f"{self.intervention.id}/responses/?search={self.participant.participant_code}"
        )
        rows = self.client.get(url).json()
        rows = rows.get("results", rows)

        self.assertEqual(len(rows), 1)
        self.assertEqual(
            rows[0]["participant"]["participant_code"],
            self.participant.participant_code,
        )


# The admin templates reference hashed static files, which only exist after a
# collectstatic run. Plain storage keeps these tests about the admin config.
@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    }
)
class CertificateAdminTests(TestCase):
    """
    Certificates are visible in the Django admin, and issued ones are
    read-only there.
    """

    def setUp(self):
        from accounts.models import CustomUser

        self.admin = CustomUser.objects.create_superuser(
            username="root@example.com",
            email="root@example.com",
            password="pw-for-tests",
        )
        self.org, self.owner = make_org("Cert Org", "cert@example.com")
        self.program = HealthProgram.objects.create(
            organization=self.org,
            program_name="Graduation Day",
            start_date=date.today(),
            target_participants=10,
            created_by=self.owner,
        )
        self.client.force_login(self.admin)

    def _template(self):
        from .models import CertificateTemplate

        return CertificateTemplate.objects.create(
            organization=self.org, name="House Style"
        )

    def _certificate(self):
        from .models import IssuedCertificate

        return IssuedCertificate.objects.create(
            program=self.program,
            template=self._template(),
            recipient_name="Ama Mensah",
            recipient_email="ama@example.com",
            verification_hash="h" * 64,
            verification_code="ABC123",
        )

    def test_certificate_templates_are_listed(self):
        self._template()
        response = self.client.get("/crt/communities/certificatetemplate/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "House Style")

    def test_a_template_can_be_opened_and_edited(self):
        template = self._template()
        response = self.client.get(
            f"/crt/communities/certificatetemplate/{template.id}/change/"
        )
        self.assertEqual(response.status_code, 200)

    def test_issued_certificates_are_listed(self):
        self._certificate()
        response = self.client.get("/crt/communities/issuedcertificate/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ABC123")
        self.assertContains(response, "Ama Mensah")

    def test_issued_certificates_are_searchable_by_verification_code(self):
        self._certificate()
        response = self.client.get(
            "/crt/communities/issuedcertificate/?q=ABC123"
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ama Mensah")

    def test_an_issued_certificate_cannot_be_added_by_hand(self):
        """One minted here would have no file and no valid hash."""
        response = self.client.get("/crt/communities/issuedcertificate/add/")
        self.assertEqual(response.status_code, 403)

    def test_an_issued_certificate_cannot_be_edited(self):
        """
        The verification hash and code are what the public verification page
        checks; editing either would silently invalidate a certificate already
        in someone's hands.
        """
        from .models import IssuedCertificate

        certificate = self._certificate()
        url = f"/crt/communities/issuedcertificate/{certificate.id}/change/"

        # Viewable...
        self.assertEqual(self.client.get(url).status_code, 200)

        # ...but not writable.
        self.client.post(
            url,
            {
                "recipient_name": "Someone Else",
                "verification_code": "HACKED",
            },
        )
        certificate.refresh_from_db()
        self.assertEqual(certificate.recipient_name, "Ama Mensah")
        self.assertEqual(certificate.verification_code, "ABC123")
        self.assertEqual(IssuedCertificate.objects.count(), 1)


class CertificateLogoTests(TestCase):
    """
    Co-branding on the issued certificate: the organisation's logo beside the
    BridgeCare mark, and the BridgeCare mark alone when there is none.
    """

    def setUp(self):
        self.org, self.owner = make_org("Logo Org", "logo@example.com")
        self.program = HealthProgram.objects.create(
            organization=self.org,
            program_name="Graduation Day",
            start_date=date.today(),
            target_participants=10,
            created_by=self.owner,
        )

    @staticmethod
    def _png_bytes(color="#123456", size=(240, 90)):
        import io

        from PIL import Image

        buf = io.BytesIO()
        Image.new("RGB", size, color).save(buf, format="PNG")
        return buf.getvalue()

    def _certificate(self, code="LOGO01"):
        from .models import IssuedCertificate

        return IssuedCertificate.objects.create(
            program=self.program,
            recipient_name="Ama Mensah",
            recipient_email="ama@example.com",
            verification_hash=code.ljust(64, "h"),
            verification_code=code,
        )

    def _attach_org_logo(self):
        from django.core.files.base import ContentFile

        self.org.orgnaization_logo.save(
            "org-logo.png", ContentFile(self._png_bytes()), save=True
        )
        self.org.refresh_from_db()

    def test_a_certificate_renders_without_an_organisation_logo(self):
        """The common case must keep working untouched."""
        from .certificate_generator import generate_certificate_pdf

        pdf = generate_certificate_pdf(self._certificate())
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertGreater(len(pdf), 1000)

    def test_the_organisation_logo_is_embedded_when_uploaded(self):
        """
        A logo adds an image stream, so the document grows. Comparing the two
        renders is what proves it was actually drawn rather than skipped by
        the generator's catch-all error handling.
        """
        from .certificate_generator import generate_certificate_pdf

        without = generate_certificate_pdf(self._certificate("NOLOGO"))
        self._attach_org_logo()
        with_logo = generate_certificate_pdf(self._certificate("WITHLOGO"))

        self.assertTrue(with_logo.startswith(b"%PDF"))
        self.assertGreater(
            len(with_logo),
            len(without),
            "the organisation logo does not appear to have been drawn",
        )

    def test_the_context_carries_the_logo_only_when_one_exists(self):
        from .certificate_generator import generate_certificate_pdf

        # Sanity on the wiring the renderer depends on.
        self.assertFalse(bool(self.org.orgnaization_logo))
        self._attach_org_logo()
        self.assertTrue(bool(self.org.orgnaization_logo))
        self.assertTrue(
            generate_certificate_pdf(self._certificate("CTX1")).startswith(b"%PDF")
        )

    def test_a_missing_logo_file_does_not_break_issuance(self):
        """
        The DB can reference a file that is no longer stored. A certificate
        must still be issued — and must not reserve space for a logo that
        cannot be drawn, which would push the BridgeCare mark off centre.
        """
        from django.core.files.storage import default_storage

        from .certificate_generator import _logo_source, generate_certificate_pdf

        self._attach_org_logo()
        default_storage.delete(self.org.orgnaization_logo.name)
        self.org.refresh_from_db()

        self.assertIsNone(_logo_source(self.org.orgnaization_logo))
        pdf = generate_certificate_pdf(self._certificate("BROKEN"))
        self.assertTrue(pdf.startswith(b"%PDF"))

    def test_a_path_only_resolver_would_have_missed_the_logo(self):
        """
        Pins down why the old renderer never showed an organisation logo: this
        project's default storage does not expose a filesystem path, so the
        `.path`-based lookup raised and was swallowed by the generator's
        catch-all. Reading through the file object is what fixed it.
        """
        from .certificate_generator import _logo_source

        self._attach_org_logo()
        logo = self.org.orgnaization_logo

        with self.assertRaises(NotImplementedError):
            logo.path  # noqa: B018 — the old code path

        self.assertIsNotNone(_logo_source(logo))

    def test_logo_source_reads_storage_backed_files(self):
        """
        Remote storage has no local `.path`. Reading through the file object
        is what makes co-branding work in production rather than only on a
        developer's machine.
        """
        import io

        from django.core.files.base import ContentFile

        from .certificate_generator import _logo_source

        class NoPathFile(ContentFile):
            """Mimics a storage backend that cannot expose a filesystem path."""

            @property
            def path(self):
                raise NotImplementedError("remote storage has no local path")

        resolved = _logo_source(NoPathFile(self._png_bytes(), name="remote.png"))
        self.assertIsInstance(resolved, io.BytesIO)
        self.assertTrue(resolved.getvalue().startswith(b"\x89PNG"))

    def test_logo_source_returns_none_for_no_logo(self):
        from .certificate_generator import _logo_source

        self.assertIsNone(_logo_source(None))
        self.assertIsNone(_logo_source(""))


class RegenerateCertificatesCommandTests(TestCase):
    """
    Stored certificate PDFs can be re-rendered after a design change.

    The PDF is written once by the issuance task and then served from storage
    forever — the download view only generates when the file is missing — so
    without this an organisation that uploads its logo after issuing keeps
    handing out logo-less certificates.
    """

    def setUp(self):
        from io import BytesIO

        from django.core.files.base import ContentFile
        from PIL import Image

        self.org, self.owner = make_org("Regen Org", "regen@example.com")
        buf = BytesIO()
        Image.new("RGB", (240, 90), "#123456").save(buf, format="PNG")
        self.org.orgnaization_logo.save(
            "logo.png", ContentFile(buf.getvalue()), save=True
        )

        self.program = HealthProgram.objects.create(
            organization=self.org,
            program_name="Graduation Day",
            start_date=date.today(),
            target_participants=10,
            created_by=self.owner,
        )

        from .models import IssuedCertificate

        self.cert = IssuedCertificate.objects.create(
            program=self.program,
            recipient_name="Ama Mensah",
            recipient_email="ama@example.com",
            verification_hash="r" * 64,
            verification_code="REGEN1",
        )
        # Stand in for a PDF rendered by an older version of the design.
        self.cert.certificate_file.save(
            "certificate_REGEN1.pdf", ContentFile(b"%PDF-1.4 stale"), save=True
        )

    def _call(self, **kwargs):
        from io import StringIO

        from django.core.management import call_command

        out = StringIO()
        call_command("regenerate_certificates", stdout=out, stderr=out, **kwargs)
        return out.getvalue()

    def _stored(self):
        self.cert.refresh_from_db()
        self.cert.certificate_file.open("rb")
        try:
            return self.cert.certificate_file.read()
        finally:
            self.cert.certificate_file.close()

    def test_it_re_renders_a_stale_pdf(self):
        self.assertEqual(self._stored(), b"%PDF-1.4 stale")

        self._call(code="REGEN1")

        refreshed = self._stored()
        self.assertTrue(refreshed.startswith(b"%PDF"))
        self.assertGreater(len(refreshed), 1000)

    def test_the_verification_code_and_hash_are_untouched(self):
        """
        Certificates already in people's hands must still verify against the
        same code — only the rendered file may change.
        """
        original_code = self.cert.verification_code
        original_hash = self.cert.verification_hash

        self._call(code="REGEN1")

        self.cert.refresh_from_db()
        self.assertEqual(self.cert.verification_code, original_code)
        self.assertEqual(self.cert.verification_hash, original_hash)

    def test_a_dry_run_changes_nothing(self):
        self._call(code="REGEN1", dry_run=True)
        self.assertEqual(self._stored(), b"%PDF-1.4 stale")

    def test_it_can_target_an_organisation(self):
        output = self._call(organization="Regen Org")
        self.assertIn("REGEN1", output)
        self.assertTrue(self._stored().startswith(b"%PDF"))

    def test_it_refuses_to_re_render_everything_by_accident(self):
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError):
            self._call()

    def test_it_reports_when_the_organisation_logo_is_included(self):
        output = self._call(code="REGEN1", dry_run=True)
        self.assertIn("with organisation logo", output)


class VolunteerEligibilityApiTests(TestCase):
    """
    Item n — the eligibility flag has to survive the API, not just the model.

    `open_to_non_professionals` was absent from `LocumJobCreateSerializer`, so
    it was silently dropped on create: a role could only ever be opened up by
    a later edit, and the creation form had nothing to bind to.
    """

    def setUp(self):
        self.org, self.owner = make_org("Eligibility Org", "elig@example.com")
        self.client.force_login(self.owner)
        self.url = f"/communities/{self.org.id}/locum-jobs/"

    def _payload(self, **overrides):
        payload = {
            "organization": str(self.org.id),
            "title": "Registration Desk Helper",
            "description": "Sign participants in at the gate.",
            "location": "Accra",
            "job_type": "volunteering",
            "open_to_non_professionals": True,
            # DRF reads a *missing* boolean in form data as False (an
            # unchecked HTML checkbox sends nothing), so mirror what the
            # client actually posts rather than relying on model defaults.
            "is_active": True,
            "approved": True,
        }
        payload.update(overrides)
        return payload

    def test_creating_an_open_volunteer_role_keeps_the_flag(self):
        from .models import LocumJob

        response = self.client.post(self.url, self._payload())
        self.assertIn(response.status_code, (200, 201), response.content[:400])

        job = LocumJob.objects.get(title="Registration Desk Helper")
        self.assertTrue(job.open_to_non_professionals)
        self.assertTrue(job.accepts_non_professionals)

    def test_a_volunteer_role_can_still_be_restricted(self):
        from .models import LocumJob

        self.client.post(
            self.url,
            self._payload(
                title="Volunteer Nurse", open_to_non_professionals=False
            ),
        )
        job = LocumJob.objects.get(title="Volunteer Nurse")
        self.assertFalse(job.open_to_non_professionals)
        self.assertFalse(job.accepts_non_professionals)

    def test_a_paid_role_is_never_stored_as_open(self):
        """
        `accepts_non_professionals` already ignored the flag on paid roles, but
        storing a True the platform quietly overrides makes the admin and the
        API disagree with the actual behaviour.
        """
        from .models import LocumJob

        response = self.client.post(
            self.url,
            self._payload(
                title="Paid Nurse",
                job_type="paid",
                renumeration="500",
                renumeration_frequency="daily",
                open_to_non_professionals=True,
            ),
        )
        self.assertIn(response.status_code, (200, 201), response.content[:400])

        job = LocumJob.objects.get(title="Paid Nurse")
        self.assertFalse(job.open_to_non_professionals)
        self.assertFalse(job.accepts_non_professionals)

    def test_switching_a_volunteer_role_to_paid_closes_it(self):
        """An edit must not leave a paid role flagged open."""
        from .models import LocumJob

        self.client.post(self.url, self._payload())
        job = LocumJob.objects.get(title="Registration Desk Helper")
        self.assertTrue(job.open_to_non_professionals)

        response = self.client.patch(
            f"{self.url}{job.id}/",
            data={
                "job_type": "paid",
                "renumeration": "500",
                "renumeration_frequency": "daily",
            },
            content_type="application/json",
        )
        self.assertIn(response.status_code, (200, 202), response.content[:400])

        job.refresh_from_db()
        self.assertFalse(job.open_to_non_professionals)

    def test_a_locum_job_needs_no_event(self):
        """
        Standing roles — a pharmacy shop attendant, a receptionist — are not
        tied to a programme. The link is the separate HealthProgramLocumNeed
        join, so a job with no join row is simply unattached.
        """
        from .models import HealthProgramLocumNeed, LocumJob

        response = self.client.post(
            self.url, self._payload(title="Pharmacy Shop Attendant")
        )
        self.assertIn(response.status_code, (200, 201), response.content[:400])

        job = LocumJob.objects.get(title="Pharmacy Shop Attendant")
        self.assertFalse(
            HealthProgramLocumNeed.objects.filter(locum_job=job).exists()
        )
        self.assertTrue(job.is_active)


class PlatformTemplateSeedingOnDeployTests(TestCase):
    """
    Templates must exist on a freshly deployed database.

    Deployment runs `migrate` but not the seeding command, so a new test or
    production environment came up with an empty template list. A data
    migration now seeds them, which means these tests run against an already
    seeded database — exactly the state a deploy produces.
    """

    def test_templates_exist_without_running_the_command(self):
        from .models import InterventionTemplate

        templates = InterventionTemplate.objects.filter(is_platform_default=True)
        self.assertGreaterEqual(
            templates.count(),
            5,
            "the migration did not seed the platform templates",
        )
        self.assertGreater(
            templates.get(name="General Health Screening").fields.count(),
            0,
            "templates were created without their fields",
        )

    def test_the_migration_seeded_usable_field_definitions(self):
        """
        The definitions are plain strings so a migration can use historical
        models; that only holds while the strings match the real choices.
        """
        from .models import InterventionField, InterventionTemplate

        general = InterventionTemplate.objects.get(name="General Health Screening")

        bmi = general.fields.get(field_key=InterventionField.FieldKey.BMI)
        self.assertTrue(bmi.is_computed)
        self.assertEqual(bmi.section, InterventionField.Section.VITALS)

        bp = general.fields.get(field_key=InterventionField.FieldKey.BLOOD_PRESSURE)
        self.assertEqual(bp.field_type, InterventionField.FieldType.TEXT)

    def test_every_seeded_string_matches_a_real_choice(self):
        """
        Guards the cost of the model-independent data module: a renamed choice
        must fail here rather than silently seeding values the app rejects.
        """
        from .intervention_template_data import TEMPLATES
        from .models import InterventionField

        sections = set(dict(InterventionField.Section.choices))
        types = set(dict(InterventionField.FieldType.choices))
        keys = set(dict(InterventionField.FieldKey.choices))

        for template in TEMPLATES:
            for field in template["fields"]:
                label = f"{template['name']} / {field['name']}"
                self.assertIn(field.get("section", "INTERVENTION"), sections, label)
                self.assertIn(field.get("field_type", "TEXT"), types, label)
                if field.get("field_key"):
                    self.assertIn(field["field_key"], keys, label)

    def test_re_running_the_command_does_not_duplicate_seeded_templates(self):
        """A deploy seeds; an operator may still run the command afterwards."""
        from django.core.management import call_command

        from .models import InterventionTemplate

        before = InterventionTemplate.objects.filter(is_platform_default=True).count()
        call_command("seed_intervention_templates", verbosity=0)
        after = InterventionTemplate.objects.filter(is_platform_default=True).count()
        self.assertEqual(before, after)

    def test_re_running_leaves_existing_template_fields_alone(self):
        """
        Organisers copy these into live interventions. A re-run must not
        rewrite fields under an event that is already running.
        """
        from django.core.management import call_command

        from .models import InterventionTemplate

        general = InterventionTemplate.objects.get(name="General Health Screening")
        field = general.fields.first()
        field.name = "Renamed by an organiser"
        field.save()

        call_command("seed_intervention_templates", verbosity=0)

        field.refresh_from_db()
        self.assertEqual(field.name, "Renamed by an organiser")

    def test_reset_replaces_the_fields(self):
        from django.core.management import call_command

        from .models import InterventionTemplate

        general = InterventionTemplate.objects.get(name="General Health Screening")
        general.fields.all().delete()
        self.assertEqual(general.fields.count(), 0)

        call_command("seed_intervention_templates", "--reset", verbosity=0)

        general.refresh_from_db()
        self.assertGreater(general.fields.count(), 0)
