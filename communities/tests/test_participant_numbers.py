"""
Per-event participant numbers.

A participant cannot remember "JTQFV". They can remember "I am number 3". The
number restarts at 1 for every event, so it stays short. Staff type 3, 003, 20
or 020 into the box that already accepts a code, a phone number and a name.

Identity is scoped to one event. A person who attends a second event is
registered again there and holds a second row, so staff never see another
event's data while working at this one.
"""

from datetime import date, timedelta

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from accounts.models import CustomUser
from communities.models import (
    HealthProgram,
    InterventionField,
    InterventionResponse,
    Participant,
    ProgramIntervention,
    ProgramInterventionType,
    format_participant_number,
)
from communities.sync import assign_participant_number, parse_participant_number, sync_batch
from .test_review_items import make_org


class NumberParsingTests(TestCase):
    """The rule that decides whether a search term is a number."""

    def test_plain_digits_and_padded_digits_read_the_same(self):
        for term, expected in [("3", 3), ("003", 3), ("20", 20), ("020", 20)]:
            self.assertEqual(parse_participant_number(term), expected, term)

    def test_the_full_printed_form_reads_as_its_number(self):
        self.assertEqual(parse_participant_number("JTQFV-003"), 3)

    def test_a_phone_number_is_not_read_as_a_participant_number(self):
        """
        The guard that matters. Without the digit bound, 0244123456 would read
        as participant number 244123456 and shadow a real phone match.
        """
        self.assertIsNone(parse_participant_number("0244123456"))
        self.assertIsNone(parse_participant_number("+233244123456"))

    def test_a_name_or_a_code_is_not_a_number(self):
        for term in ["Ama", "JTQFV", "", None, "  ", "0", "000"]:
            self.assertIsNone(parse_participant_number(term), term)


class DisplayCodeTests(TestCase):
    def test_the_number_is_padded_but_never_truncated(self):
        self.assertEqual(format_participant_number("JTQFV", 1), "JTQFV-001")
        self.assertEqual(format_participant_number("JTQFV", 12), "JTQFV-012")
        self.assertEqual(format_participant_number("JTQFV", 1234), "JTQFV-1234")

    def test_a_participant_with_no_number_shows_the_bare_code(self):
        self.assertEqual(format_participant_number("JTQFV", None), "JTQFV")


class EventFixture(TestCase):
    """Shared setup: one organisation, two events, one intervention each."""

    def setUp(self):
        self.org, self.owner = make_org("Number Org", "numbers@example.com")
        self.itype = ProgramInterventionType.objects.create(name="Screening")

        self.program_a = self._program("Event A")
        self.program_b = self._program("Event B")
        self.iv_a1 = self._intervention(self.program_a, "A1")
        self.iv_a2 = self._intervention(self.program_a, "A2")
        self.iv_b1 = self._intervention(self.program_b, "B1")

    def _program(self, name):
        return HealthProgram.objects.create(
            organization=self.org,
            program_name=name,
            start_date=date.today(),
            target_participants=50,
            location_name="Accra",
            created_by=self.owner,
        )

    def _intervention(self, program, title):
        intervention = ProgramIntervention.objects.create(
            intervention_type=self.itype, program=program, title=title
        )
        InterventionField.objects.create(
            intervention=intervention,
            name="Notes",
            field_type=InterventionField.FieldType.TEXT,
        )
        return intervention

    def _participant(self, program, name="Ama", phone=None):
        return Participant.objects.create(
            organization=self.org, program=program, fullname=name, phone_number=phone
        )


class AllocationTests(EventFixture):
    def test_the_number_restarts_at_each_event(self):
        """The whole point. Numbers stay small enough to remember."""
        ama_at_a = self._participant(self.program_a, "Ama")
        ama_at_b = self._participant(self.program_b, "Ama")

        self.assertEqual(assign_participant_number(self.program_a, ama_at_a), 1)
        self.assertEqual(assign_participant_number(self.program_b, ama_at_b), 1)

    def test_two_participants_at_one_event_get_1_and_2(self):
        first = self._participant(self.program_a, "Ama")
        second = self._participant(self.program_a, "Kofi")

        self.assertEqual(assign_participant_number(self.program_a, first), 1)
        self.assertEqual(assign_participant_number(self.program_a, second), 2)

    def test_allocating_twice_returns_the_same_number(self):
        """
        The participant who reaches intervention 2 must be handed back the
        number they were told at intervention 1.
        """
        ama = self._participant(self.program_a, "Ama")
        first = assign_participant_number(self.program_a, ama)
        second = assign_participant_number(self.program_a, ama)

        self.assertEqual(first, second)
        ama.refresh_from_db()
        self.assertEqual(ama.participant_number, first)

    def test_the_database_rejects_a_duplicate_number_in_one_event(self):
        """Enforced by a constraint, not only by application code."""
        first = self._participant(self.program_a, "Ama")
        first.participant_number = 1
        first.save()

        second = self._participant(self.program_a, "Kofi")
        second.participant_number = 1
        with self.assertRaises(IntegrityError), transaction.atomic():
            second.save()

    def test_the_same_number_is_allowed_at_a_different_event(self):
        first = self._participant(self.program_a, "Ama")
        first.participant_number = 1
        first.save()

        second = self._participant(self.program_b, "Yaw")
        second.participant_number = 1
        second.save()  # must not raise

        self.assertEqual(second.participant_number, 1)


class WritePathTests(EventFixture):
    """Both paths that create a record must give the person a number."""

    def _live(self, intervention, participant, answers=None):
        self.client.force_login(self.owner)
        field = intervention.fields.first()
        return self.client.post(
            f"/communities/{self.org.id}/intervention-answer/",
            data={
                "intervention": str(intervention.id),
                "participant": participant,
                "answers": answers or [{"field": str(field.id), "value": "seen"}],
            },
            content_type="application/json",
        )

    def test_the_live_path_allocates_and_returns_the_number(self):
        response = self._live(self.iv_a1, {"fullname": "Ama"})
        self.assertEqual(response.status_code, 201, response.content[:400])

        body = response.json()
        self.assertEqual(body["participant_number"], 1)
        self.assertTrue(body["participant_display_code"].endswith("-001"))

    def test_the_offline_path_allocates_a_number(self):
        """
        Catches a fix applied only to views.py. The two paths kept their own
        copies of participant resolution once before and drifted.
        """
        outcome = sync_batch(
            self.org,
            [
                {
                    "client_uuid": "11111111-1111-1111-1111-111111111111",
                    "intervention": str(self.iv_a1.id),
                    "participant": {"fullname": "Ama"},
                    "answers": [],
                }
            ],
            self.owner,
        )[0]

        self.assertEqual(outcome.status, "created", outcome.detail)
        self.assertEqual(outcome.participant_number, 1)
        self.assertTrue(outcome.participant_display_code.endswith("-001"))

    def test_a_replayed_duplicate_still_reports_the_number(self):
        """
        A device whose first request timed out keeps retrying and keeps getting
        "duplicate". Without this it never learns the number, so staff can
        never tell the participant what to say.
        """
        item = {
            "client_uuid": "22222222-2222-2222-2222-222222222222",
            "intervention": str(self.iv_a1.id),
            "participant": {"fullname": "Ama"},
            "answers": [],
        }
        sync_batch(self.org, [item], self.owner)
        replay = sync_batch(self.org, [item], self.owner)[0]

        self.assertEqual(replay.status, "duplicate")
        self.assertEqual(replay.participant_number, 1)

    def test_a_merged_record_still_gets_a_number(self):
        """
        A nurse and a doctor recording one person arrive as two items. Only the
        first creates a response. The person needs a number either way. Catches
        allocation placed inside the create branch.
        """
        base = {
            "intervention": str(self.iv_a1.id),
            "participant": {"fullname": "Ama", "phone_number": "+233200000001"},
            "answers": [],
        }
        first = sync_batch(
            self.org,
            [dict(base, client_uuid="33333333-3333-3333-3333-333333333333")],
            self.owner,
        )[0]
        second = sync_batch(
            self.org,
            [dict(base, client_uuid="44444444-4444-4444-4444-444444444444")],
            self.owner,
        )[0]

        self.assertEqual(second.status, "merged", second.detail)
        self.assertEqual(first.participant_number, 1)
        self.assertEqual(second.participant_number, 1)

    def test_the_second_intervention_of_one_event_keeps_the_number(self):
        """The requirement stated verbatim."""
        self._live(self.iv_a1, {"fullname": "Ama", "phone_number": "+233200000002"})
        response = self._live(
            self.iv_a2, {"fullname": "Ama", "phone_number": "+233200000002"}
        )

        self.assertEqual(response.json()["participant_number"], 1)
        self.assertEqual(
            Participant.objects.filter(program=self.program_a).count(), 1
        )

    def test_a_person_at_a_second_event_is_a_new_participant(self):
        """
        Events are fully separate. The person is registered again at event B
        and holds a second row with its own number.
        """
        self._live(self.iv_a1, {"fullname": "Ama", "phone_number": "+233200000003"})
        self._live(self.iv_b1, {"fullname": "Ama", "phone_number": "+233200000003"})

        self.assertEqual(Participant.objects.filter(program=self.program_a).count(), 1)
        self.assertEqual(Participant.objects.filter(program=self.program_b).count(), 1)


class CrossOrganizationTests(EventFixture):
    def test_a_phone_number_never_matches_another_organisations_participant(self):
        """
        The id and code branches always filtered by organisation. The phone
        branch did not, so organisation A could attach a record to
        organisation B's participant and overwrite their details.
        """
        other_org, other_owner = make_org("Elsewhere", "elsewhere@example.com")
        other_program = HealthProgram.objects.create(
            organization=other_org,
            program_name="Their Event",
            start_date=date.today(),
            target_participants=10,
            location_name="Kumasi",
            created_by=other_owner,
        )
        theirs = Participant.objects.create(
            organization=other_org,
            program=other_program,
            fullname="Theirs",
            phone_number="+233200000009",
        )

        sync_batch(
            self.org,
            [
                {
                    "client_uuid": "55555555-5555-5555-5555-555555555555",
                    "intervention": str(self.iv_a1.id),
                    "participant": {
                        "fullname": "Mine",
                        "phone_number": "+233200000009",
                    },
                    "answers": [],
                }
            ],
            self.owner,
        )

        theirs.refresh_from_db()
        self.assertEqual(theirs.fullname, "Theirs")
        self.assertIsNone(theirs.participant_number)


class LookupTests(EventFixture):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.owner)
        self.url = f"/communities/{self.org.id}/participants/lookup/"

        self.ama = self._participant(self.program_a, "Ama Mensah")
        self.ama.participant_number = 3
        self.ama.save()

        self.kofi = self._participant(self.program_a, "Kofi", phone="+233244123456")
        self.kofi.participant_number = 24
        self.kofi.save()

        self.stranger = self._participant(self.program_b, "Stranger")
        self.stranger.participant_number = 3
        self.stranger.save()

    def _get(self, **params):
        return self.client.get(self.url, params)

    def test_plain_digits_find_the_participant(self):
        response = self._get(code="3", program=str(self.program_a.id))
        self.assertEqual(response.status_code, 200, response.content[:300])
        self.assertEqual(response.json()["participant"]["fullname"], "Ama Mensah")

    def test_padded_digits_find_the_same_participant(self):
        response = self._get(code="003", program=str(self.program_a.id))
        self.assertEqual(response.json()["participant"]["fullname"], "Ama Mensah")

    def test_a_number_from_another_event_is_never_returned(self):
        """A wrong-patient bug, not a search bug."""
        response = self._get(code="3", program=str(self.program_b.id))
        self.assertEqual(response.json()["participant"]["fullname"], "Stranger")

    def test_digits_prefer_the_number_over_a_matching_phone_number(self):
        """
        Kofi holds number 24 and Ama's neighbour holds a phone containing 24.
        The order must be the number first, not whichever row sorts first.
        """
        response = self._get(code="24", program=str(self.program_a.id))
        self.assertEqual(response.json()["participant"]["fullname"], "Kofi")

    def test_a_long_digit_string_still_reads_as_a_phone_number(self):
        response = self._get(code="0244123456", program=str(self.program_a.id))
        self.assertEqual(response.status_code, 200, response.content[:300])
        self.assertEqual(response.json()["participant"]["fullname"], "Kofi")

    def test_the_full_printed_form_resolves(self):
        response = self._get(
            code=f"{self.ama.participant_code}-003", program=str(self.program_a.id)
        )
        self.assertEqual(response.json()["participant"]["fullname"], "Ama Mensah")

    def test_digits_without_an_event_explain_what_is_missing(self):
        response = self._get(code="3")
        self.assertEqual(response.status_code, 404)
        self.assertIn("name the event", response.json()["message"])

    def test_the_intervention_can_stand_in_for_the_event(self):
        response = self._get(code="3", intervention=str(self.iv_a1.id))
        self.assertEqual(response.status_code, 200, response.content[:300])
        self.assertEqual(response.json()["participant"]["fullname"], "Ama Mensah")

    def test_the_response_carries_the_number_and_the_display_code(self):
        payload = self._get(code="3", program=str(self.program_a.id)).json()
        self.assertEqual(payload["participant"]["participant_number"], 3)
        self.assertTrue(payload["participant"]["display_code"].endswith("-003"))

    def test_an_ambiguous_name_offers_the_choices(self):
        """
        The endpoint used to refuse. A participant with no phone number who
        forgot their number could then not be found at all, and staff created a
        duplicate record.
        """
        twin = self._participant(self.program_a, "Ama Owusu")
        twin.participant_number = 9
        twin.save()

        response = self._get(code="Ama", program=str(self.program_a.id))
        self.assertEqual(response.status_code, 300)

        body = response.json()
        numbers = sorted(c["participant_number"] for c in body["candidates"])
        self.assertEqual(numbers, [3, 9])


class BrowseTests(EventFixture):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.owner)
        for index, name in enumerate(["Ama", "Kofi", "Yaw"], start=1):
            participant = self._participant(self.program_a, name)
            participant.participant_number = index
            participant.save()
        self._participant(self.program_b, "Stranger").save()

    def test_the_list_returns_this_events_participants_in_number_order(self):
        response = self.client.get(
            f"/communities/{self.org.id}/programs/{self.program_a.id}/participants/"
        )
        self.assertEqual(response.status_code, 200, response.content[:300])

        body = response.json()
        self.assertEqual(body["count"], 3)
        self.assertEqual(
            [p["participant_number"] for p in body["participants"]], [1, 2, 3]
        )

    def test_the_list_never_shows_another_events_participants(self):
        response = self.client.get(
            f"/communities/{self.org.id}/programs/{self.program_a.id}/participants/"
        )
        names = [p["fullname"] for p in response.json()["participants"]]
        self.assertNotIn("Stranger", names)

    def test_the_list_can_be_filtered_by_name(self):
        response = self.client.get(
            f"/communities/{self.org.id}/programs/{self.program_a.id}/participants/",
            {"search": "Kofi"},
        )
        body = response.json()
        self.assertEqual(body["count"], 1)
        self.assertEqual(body["participants"][0]["fullname"], "Kofi")


class QueueSlipTests(EventFixture):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.owner)
        self.url = f"/communities/{self.org.id}/participants/queue-slips/"

    def test_slips_for_an_event_carry_consecutive_numbers(self):
        response = self.client.post(
            self.url,
            data={"count": 3, "program": str(self.program_a.id)},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.content[:300])

        slips = response.json()["slips"]
        self.assertEqual([s["participant_number"] for s in slips], [1, 2, 3])
        self.assertTrue(slips[0]["display_code"].endswith("-001"))

    def test_slips_without_an_event_carry_no_number_and_say_so(self):
        """`program` has always been optional. Existing clients send nothing."""
        response = self.client.post(
            self.url, data={"count": 2}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 201, response.content[:300])

        body = response.json()
        self.assertTrue(all(s["participant_number"] is None for s in body["slips"]))
        self.assertIn("warning", body)

    def test_a_slip_filled_in_later_keeps_its_printed_number(self):
        """
        The entire reason for printing numbers ahead of time. Catches an
        allocator that overwrites instead of returning what is already held.
        """
        slips = self.client.post(
            self.url,
            data={"count": 2, "program": str(self.program_a.id)},
            content_type="application/json",
        ).json()["slips"]
        second_slip = slips[1]

        field = self.iv_a1.fields.first()
        response = self.client.post(
            f"/communities/{self.org.id}/intervention-answer/",
            data={
                "intervention": str(self.iv_a1.id),
                "participant_id": second_slip["participant_id"],
                "participant": {"fullname": "Ama"},
                "answers": [{"field": str(field.id), "value": "seen"}],
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.content[:400])
        self.assertEqual(response.json()["participant_number"], 2)


class ResponsesSearchTests(EventFixture):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.owner)

        self.ama = self._participant(self.program_a, "Ama")
        self.ama.participant_number = 1
        self.ama.save()
        self.kofi = self._participant(self.program_a, "Kofi")
        self.kofi.participant_number = 2
        self.kofi.save()

        for participant in (self.ama, self.kofi):
            InterventionResponse.objects.create(
                intervention=self.iv_a1, participant=participant
            )

    def _search(self, term):
        response = self.client.get(
            f"/communities/{self.org.id}/interventions/{self.iv_a1.id}/responses/",
            {"search": term},
        )
        self.assertEqual(response.status_code, 200, response.content[:300])
        body = response.json()
        return body.get("results", body)

    def test_searching_a_number_returns_exactly_that_participant(self):
        rows = self._search("1")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["participant"]["fullname"], "Ama")

    def test_searching_a_padded_number_works(self):
        rows = self._search("002")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["participant"]["fullname"], "Kofi")

    def test_name_and_code_search_still_work(self):
        self.assertEqual(len(self._search("Kofi")), 1)
        self.assertEqual(len(self._search(self.ama.participant_code)), 1)

    def test_the_row_carries_the_number_and_the_display_code(self):
        rows = self._search("1")
        self.assertEqual(rows[0]["participant"]["participant_number"], 1)
        self.assertTrue(rows[0]["participant"]["display_code"].endswith("-001"))


class BackfillTests(EventFixture):
    """Existing rows predate both the event link and the number."""

    def _legacy(self, name, phone=None):
        """A participant as they existed before this change: no event, no number."""
        return Participant.objects.create(
            organization=self.org, fullname=name, phone_number=phone
        )

    def _record(self, intervention, participant, when):
        response = InterventionResponse.objects.create(
            intervention=intervention, participant=participant
        )
        InterventionResponse.objects.filter(pk=response.pk).update(recorded_at=when)
        return response

    def _run(self):
        from communities.backfill import backfill_participant_numbers

        return backfill_participant_numbers(
            participant_model=Participant, response_model=InterventionResponse
        )

    def test_numbers_follow_the_order_people_were_first_recorded(self):
        """
        Orders on `recorded_at`, not on the typing time. A day of paper slips
        transcribed in the evening shares one creation time and keeps the real
        arrival order only in `recorded_at`.
        """
        now = timezone.now()
        late = self._legacy("Late")
        early = self._legacy("Early")

        self._record(self.iv_a1, late, now)
        self._record(self.iv_a1, early, now - timedelta(hours=3))

        self._run()

        early.refresh_from_db()
        late.refresh_from_db()
        self.assertEqual(early.participant_number, 1)
        self.assertEqual(late.participant_number, 2)

    def test_a_participant_recorded_at_two_events_is_split(self):
        """
        Identity is per event now. One legacy row with records at two events
        must become two rows, and each event's records must follow.
        """
        now = timezone.now()
        person = self._legacy("Ama", phone="+233200000004")
        self._record(self.iv_a1, person, now - timedelta(days=2))
        self._record(self.iv_b1, person, now)

        split, _ = self._run()
        self.assertEqual(split, 1)

        at_a = Participant.objects.get(program=self.program_a, fullname="Ama")
        at_b = Participant.objects.get(program=self.program_b, fullname="Ama")
        self.assertNotEqual(at_a.pk, at_b.pk)
        self.assertNotEqual(at_a.participant_code, at_b.participant_code)

        # Each event's records point at that event's row.
        self.assertEqual(
            InterventionResponse.objects.get(intervention=self.iv_a1).participant_id,
            at_a.pk,
        )
        self.assertEqual(
            InterventionResponse.objects.get(intervention=self.iv_b1).participant_id,
            at_b.pk,
        )

    def test_a_split_participant_is_numbered_at_both_events(self):
        now = timezone.now()
        person = self._legacy("Ama")
        self._record(self.iv_a1, person, now - timedelta(days=2))
        self._record(self.iv_b1, person, now)

        self._run()

        self.assertEqual(
            Participant.objects.get(program=self.program_a).participant_number, 1
        )
        self.assertEqual(
            Participant.objects.get(program=self.program_b).participant_number, 1
        )

    def test_participants_with_no_records_are_left_alone(self):
        """Unused slips and orphan rows. There is no event to place them in."""
        orphan = self._legacy("Never seen")
        self._run()

        orphan.refresh_from_db()
        self.assertIsNone(orphan.participant_number)
        self.assertIsNone(orphan.program_id)

    def test_running_it_twice_changes_nothing(self):
        """
        A re-run must not renumber someone who has already been told their
        number, and must not raise on the unique constraint.
        """
        now = timezone.now()
        for index, name in enumerate(["Ama", "Kofi", "Yaw"]):
            person = self._legacy(name)
            self._record(self.iv_a1, person, now + timedelta(minutes=index))

        self._run()
        before = dict(
            Participant.objects.values_list("fullname", "participant_number")
        )

        self._run()
        after = dict(Participant.objects.values_list("fullname", "participant_number"))

        self.assertEqual(before, after)
        self.assertEqual(sorted(before.values()), [1, 2, 3])

    def test_a_record_with_no_participant_does_not_break_the_run(self):
        """Both FKs are SET_NULL, so such rows genuinely exist."""
        now = timezone.now()
        person = self._legacy("Ama")
        self._record(self.iv_a1, person, now)
        InterventionResponse.objects.create(intervention=self.iv_a1, participant=None)

        self._run()  # must not raise

        person.refresh_from_db()
        self.assertEqual(person.participant_number, 1)


class PhoneSearchTests(EventFixture):
    """
    The phone column stores the national format with spaces, for example
    "024 412 3456". Staff type "0244123456". A plain `icontains` between the
    two matches nothing, so phone search found nobody at all.
    """

    def setUp(self):
        super().setUp()
        self.client.force_login(self.owner)
        self.kofi = self._participant(
            self.program_a, "Kofi", phone="+233244123456"
        )
        self.kofi.participant_number = 7
        self.kofi.save()

    def test_the_column_really_does_store_separators(self):
        """Pins the cause, so the fix is not later mistaken for guesswork."""
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT phone_number FROM communities_participant WHERE id = %s",
                [str(self.kofi.id)],
            )
            stored = cursor.fetchone()[0]

        self.assertIn(" ", stored)
        self.assertNotIn("0244123456", stored)

    def test_lookup_finds_a_number_typed_the_way_staff_write_it(self):
        response = self.client.get(
            f"/communities/{self.org.id}/participants/lookup/",
            {"code": "0244123456", "program": str(self.program_a.id)},
        )
        self.assertEqual(response.status_code, 200, response.content[:300])
        self.assertEqual(response.json()["participant"]["fullname"], "Kofi")

    def test_lookup_finds_a_number_typed_internationally(self):
        response = self.client.get(
            f"/communities/{self.org.id}/participants/lookup/",
            {"code": "+233244123456", "program": str(self.program_a.id)},
        )
        self.assertEqual(response.status_code, 200, response.content[:300])
        self.assertEqual(response.json()["participant"]["fullname"], "Kofi")

    def test_the_responses_search_finds_a_phone_number_too(self):
        InterventionResponse.objects.create(
            intervention=self.iv_a1, participant=self.kofi
        )
        response = self.client.get(
            f"/communities/{self.org.id}/interventions/{self.iv_a1.id}/responses/",
            {"search": "0244123456"},
        )
        self.assertEqual(response.status_code, 200, response.content[:300])
        body = response.json()
        rows = body.get("results", body)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["participant"]["fullname"], "Kofi")


class ResolveByNumberTests(EventFixture):
    """
    A device that was offline cannot call the lookup. Staff type the number the
    participant says, and the record carries it. On sync the number must find
    the person, or the record creates a duplicate and their earlier vitals are
    stranded.
    """

    def test_an_offline_record_finds_the_participant_by_their_number(self):
        ama = self._participant(self.program_a, "Ama")
        assign_participant_number(self.program_a, ama)

        outcome = sync_batch(
            self.org,
            [
                {
                    "client_uuid": "66666666-6666-6666-6666-666666666666",
                    "intervention": str(self.iv_a2.id),
                    "participant": {"participant_number": "1"},
                    "answers": [],
                }
            ],
            self.owner,
        )[0]

        self.assertEqual(outcome.status, "created", outcome.detail)
        self.assertEqual(outcome.participant_number, 1)
        # One person, not two.
        self.assertEqual(Participant.objects.filter(program=self.program_a).count(), 1)

    def test_a_padded_number_resolves_the_same_way(self):
        ama = self._participant(self.program_a, "Ama")
        assign_participant_number(self.program_a, ama)

        sync_batch(
            self.org,
            [
                {
                    "client_uuid": "77777777-7777-7777-7777-777777777777",
                    "intervention": str(self.iv_a2.id),
                    "participant": {"participant_number": "001"},
                    "answers": [],
                }
            ],
            self.owner,
        )

        self.assertEqual(Participant.objects.filter(program=self.program_a).count(), 1)

    def test_a_number_never_resolves_across_events(self):
        """Number 1 exists at both events. It must not cross."""
        at_a = self._participant(self.program_a, "Ama")
        assign_participant_number(self.program_a, at_a)

        sync_batch(
            self.org,
            [
                {
                    "client_uuid": "88888888-8888-8888-8888-888888888888",
                    "intervention": str(self.iv_b1.id),
                    "participant": {"participant_number": "1", "fullname": "Stranger"},
                    "answers": [],
                }
            ],
            self.owner,
        )

        at_a.refresh_from_db()
        self.assertEqual(at_a.fullname, "Ama")
        self.assertEqual(Participant.objects.filter(program=self.program_b).count(), 1)
