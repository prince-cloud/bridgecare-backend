"""
Offline sync for outreach data entry (13 July 2026 review, items b and c).

The pilot ran on unstable connectivity: entries were lost, users were logged
out mid-form, and staff had to switch networks. The agreed model is hybrid —
record locally on the device, then synchronise automatically when connectivity
returns.

Two properties matter more than throughput here:

**Idempotency.** A request that times out has usually still been applied. The
client keeps retrying until it gets an answer, so the same item arrives more
than once as a matter of course. Every queued record carries a
client-generated `client_uuid`; replaying it returns the original result rather
than creating a second record.

**Convergence without conflict.** Several people attend to the same participant
at one event — a nurse takes vitals, a doctor adds findings afterwards. Both
devices may be offline at once. Rather than creating rival records, submissions
for the same (participant, intervention) merge into one, and individual field
values resolve last-write-wins on `recorded_at` — the time the measurement was
actually taken, not the time it happened to upload. A nurse's reading synced
late therefore cannot overwrite the doctor's later correction.
"""

import re
from dataclasses import dataclass, field as dataclass_field
from datetime import datetime
from typing import Any, Dict, List, Optional

from django.db import IntegrityError, transaction
from django.db.models import Max
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from loguru import logger

from .models import (
    HealthProgram,
    InterventionField,
    InterventionResponse,
    InterventionResponseValue,
    Organization,
    Participant,
    ProgramIntervention,
)
from .vitals import apply_derived_values


@dataclass
class SyncOutcome:
    """Result for a single queued item, echoed back so the client can dequeue."""

    client_uuid: str
    status: str  # created | merged | duplicate | failed
    response_id: Optional[str] = None
    participant_code: Optional[str] = None
    # The short number the participant remembers, and the full printed form.
    # The client reads these back to the participant after a record syncs.
    participant_number: Optional[int] = None
    participant_display_code: Optional[str] = None
    detail: str = ""
    conflicts: List[Dict[str, Any]] = dataclass_field(default_factory=list)

    def as_dict(self):
        return {
            "client_uuid": self.client_uuid,
            "status": self.status,
            "response_id": self.response_id,
            "participant_code": self.participant_code,
            "participant_number": self.participant_number,
            "participant_display_code": self.participant_display_code,
            "detail": self.detail,
            "conflicts": self.conflicts,
        }


def coerce_recorded_at(value):
    """
    Turn whatever the client sent into an aware datetime.

    This endpoint reads `request.data` directly rather than going through a
    serializer, so `recorded_at` arrives as the ISO **string** JSON carries it
    as. Conflict resolution then compared that string against the stored
    datetime and raised `'<' not supported between instances of 'str' and
    'datetime.datetime'` — which only surfaced on the *second* submission for a
    participant, because the first has nothing to merge with and never reaches
    the comparison. The record stayed queued and retried forever.

    Anything unusable falls back to now: a record with an odd timestamp is
    worth far more than a record rejected at an outreach event.
    """
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = parse_datetime(value.strip())
        except ValueError:
            parsed = None
    else:
        parsed = None

    if parsed is None:
        return timezone.now()

    # Naive input (a device with no timezone offset) is read as local time,
    # which is what a nurse's tablet clock actually means.
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


# A participant number is 1 to 4 digits. The bound is what stops a ten-digit
# Ghanaian phone number reading as participant number 244123456 and shadowing
# a real phone match. Numbers restart at every event, so they stay small.
_NUMBER_TERM = re.compile(r"^\d{1,4}$")
# The full printed form, e.g. "JTQFV-003".
_DISPLAY_CODE_TERM = re.compile(r"^(?P<code>[A-Za-z0-9]{2,20})-(?P<number>\d{1,4})$")


def parse_participant_number(term) -> Optional[int]:
    """
    Read a search term as a participant number, or return None.

    Accepts "3", "003", "20", "020" and the full printed form "JTQFV-003".
    Returns None for anything else, so the caller falls through to the code,
    the phone number and the name unchanged.
    """
    text = (term or "").strip()
    if not text:
        return None

    display = _DISPLAY_CODE_TERM.match(text)
    if display:
        text = display.group("number")

    if not _NUMBER_TERM.match(text):
        return None

    number = int(text)
    return number if number >= 1 else None


def assign_participant_number(program, participant):
    """
    Give this participant their number for this event, or return the one they
    already hold.

    Numbers restart at 1 for every event, so a participant remembers a short
    number and says it at the next intervention.

    Idempotent on purpose. The participant who reaches intervention 2 of one
    event must be handed back the number they were told at intervention 1, and
    a pre-printed slip must keep the number that was printed on it.
    """
    if program is None or participant is None:
        return None
    if participant.participant_number is not None:
        return participant.participant_number

    for _ in range(8):
        # Serialise allocation for this event across concurrent devices. This
        # is a no-op on SQLite, which is why the retry below still matters.
        HealthProgram.objects.select_for_update().filter(pk=program.pk).first()

        highest = Participant.objects.filter(program=program).aggregate(
            highest=Max("participant_number")
        )["highest"]
        candidate = (highest or 0) + 1

        try:
            # A savepoint, not the outer transaction. Both callers wrap the
            # whole request in @transaction.atomic, and on PostgreSQL an
            # unguarded IntegrityError aborts that transaction — every later
            # query in the request would fail and the device would retry the
            # item forever.
            with transaction.atomic():
                participant.program = program
                participant.participant_number = candidate
                participant.save(update_fields=["program", "participant_number"])
            return candidate
        except IntegrityError:
            participant.refresh_from_db(fields=["participant_number"])
            if participant.participant_number is not None:
                # A concurrent request numbered this participant first.
                return participant.participant_number

    logger.error(
        f"PARTICIPANT_NUMBER_ALLOCATION_FAILED program={program.pk} "
        f"participant={participant.pk}"
    )
    return None


def resolve_participant(
    program, participant_data, participant_id=None, organization=None
):
    """
    Find or create the participant for a record in this event.

    Everything is scoped to the event. A person who attends a second event is
    registered again there and holds a second row, so staff never see another
    event's data while working at this one.

    Matching order: an explicit id (a pre-printed queue slip), then the
    participant number, then the participant code, then the phone number. The
    number comes early because it is what the participant says out loud.

    Blank incoming values never overwrite stored ones: a device that captured
    only a phone number must not wipe a name recorded elsewhere.
    """
    participant = None
    data = participant_data or {}
    if organization is None and program is not None:
        organization = program.organization

    scoped = Participant.objects.filter(program=program)

    if participant_id:
        participant = scoped.filter(id=participant_id).first()

    number = parse_participant_number(data.get("participant_number"))
    if participant is None and number is not None:
        participant = scoped.filter(participant_number=number).first()

    code = (data.get("participant_code") or "").strip()
    if participant is None and code:
        participant = scoped.filter(participant_code__iexact=code).first()

    phone_number = data.get("phone_number")
    if participant is None and phone_number:
        # Scoped like every other branch. This match used to run across the
        # whole platform, so one organisation could attach a record to another
        # organisation's participant and overwrite their details.
        participant = scoped.filter(phone_number=phone_number).first()

    if participant is None:
        participant = Participant(organization=organization, program=program)
        if phone_number:
            participant.phone_number = phone_number

    if not participant.organization_id:
        participant.organization = organization
    if not participant.program_id:
        participant.program = program

    for attr in ("fullname", "email", "gender", "location", "date_of_birth", "age"):
        incoming = (participant_data or {}).get(attr)
        if incoming not in (None, ""):
            setattr(participant, attr, incoming)

    participant.save()
    return participant


def _apply_values(response, answers, recorded_at, user):
    """
    Write field values, resolving conflicts by measurement time.

    Returns the list of conflicts where an incoming value was *rejected* for
    being older than what is already stored, so the client can surface them
    rather than silently discarding the user's work.
    """
    conflicts: List[Dict[str, Any]] = []
    if not answers:
        return conflicts

    field_ids = [a.get("field") for a in answers if a.get("field")]
    fields = {
        str(f.id): f for f in InterventionField.objects.filter(id__in=field_ids)
    }

    values_by_key: Dict[str, str] = {}

    for answer in answers:
        field = fields.get(str(answer.get("field")))
        if field is None:
            continue
        # Derived values are recomputed below; never trust a client's copy.
        if field.is_computed:
            continue

        incoming_value = answer.get("value", "")
        existing = InterventionResponseValue.objects.filter(
            response=response, field=field
        ).first()

        if existing is not None:
            existing_time = existing.recorded_at or existing.last_updated
            if (
                existing_time
                and recorded_at
                and recorded_at < existing_time
                and existing.value != incoming_value
            ):
                # A newer reading is already stored. Keep it, and report the
                # rejection instead of dropping it on the floor.
                conflicts.append(
                    {
                        "field_id": str(field.id),
                        "field_name": field.name,
                        "kept_value": existing.value,
                        "rejected_value": incoming_value,
                        "kept_recorded_at": existing_time.isoformat(),
                    }
                )
                values_by_key[field.field_key or str(field.id)] = existing.value
                continue

            existing.value = incoming_value
            existing.recorded_at = recorded_at
            existing.recorded_by = user
            existing.save()
        else:
            InterventionResponseValue.objects.create(
                response=response,
                field=field,
                value=incoming_value,
                recorded_at=recorded_at,
                recorded_by=user,
            )

        if field.field_key:
            values_by_key[field.field_key] = incoming_value

    # Recompute derived values from whatever survived conflict resolution.
    write_derived_values(response, values_by_key, recorded_at, user)
    return conflicts


def write_derived_values(response, values_by_key, recorded_at=None, user=None):
    """
    Compute and store every derived value (currently BMI) for a response.

    The single place this happens. It is reached from three directions — a live
    submission, an edit, and an offline sync — and having three copies would
    mean a new derived value silently working on some paths and not others.

    Only writes fields the intervention actually configured as computed, so an
    intervention without a BMI field simply gets nothing.
    """
    derived = apply_derived_values(values_by_key)
    if not derived:
        return

    computed_fields = InterventionField.objects.filter(
        intervention=response.intervention,
        is_computed=True,
        field_key__in=list(derived.keys()),
    )
    for field in computed_fields:
        InterventionResponseValue.objects.update_or_create(
            response=response,
            field=field,
            defaults={
                "value": derived[field.field_key],
                "recorded_at": recorded_at,
                "recorded_by": user,
            },
        )


def collect_stored_values(response):
    """
    Current {field_key: value} for a response, excluding derived fields.

    Used when recomputing after an edit: derived values must be rebuilt from
    the measurements, never from a previous derivation.
    """
    stored = (
        InterventionResponseValue.objects.filter(response=response)
        .select_related("field")
        .exclude(field__isnull=True)
    )
    return {
        v.field.field_key: v.value
        for v in stored
        if v.field.field_key and not v.field.is_computed
    }


@transaction.atomic
def sync_one(organization: Organization, item: Dict[str, Any], user) -> SyncOutcome:
    """Apply a single queued record. Never raises — failures come back typed."""
    client_uuid = str(item.get("client_uuid") or "")
    if not client_uuid:
        return SyncOutcome(
            client_uuid="",
            status="failed",
            detail="client_uuid is required for offline sync.",
        )

    # Idempotency: this exact record already landed.
    existing = InterventionResponse.objects.filter(client_uuid=client_uuid).first()
    if existing is not None:
        # Echo the number as well. A device whose first request timed out keeps
        # retrying and keeps getting "duplicate"; without this it never learns
        # the number, so staff can never tell the participant what to say.
        return SyncOutcome(
            client_uuid=client_uuid,
            status="duplicate",
            response_id=str(existing.id),
            participant_code=(
                existing.participant.participant_code if existing.participant else None
            ),
            participant_number=(
                existing.participant.participant_number if existing.participant else None
            ),
            participant_display_code=(
                existing.participant.display_code if existing.participant else None
            ),
            detail="Already synced.",
        )

    intervention = ProgramIntervention.objects.filter(
        id=item.get("intervention"),
        program__organization=organization,
    ).select_related("program").first()
    if intervention is None:
        return SyncOutcome(
            client_uuid=client_uuid,
            status="failed",
            detail="Unknown intervention for this organisation.",
        )

    try:
        participant = resolve_participant(
            intervention.program,
            item.get("participant") or {},
            item.get("participant_id"),
            organization=organization,
        )
        # Before the merge lookup below, not inside the create branch. A nurse
        # and a doctor recording the same person arrive as two items; only the
        # first creates a response, but the person needs a number either way.
        assign_participant_number(intervention.program, participant)
    except Exception as exc:
        logger.error(f"Offline sync participant resolution failed: {exc}")
        return SyncOutcome(
            client_uuid=client_uuid,
            status="failed",
            detail=f"Could not resolve participant: {exc}",
        )

    recorded_at = coerce_recorded_at(item.get("recorded_at"))

    # Merge into an existing record for the same participant + intervention so
    # a nurse and a doctor attending the same person produce one record, not
    # two competing ones.
    response = InterventionResponse.objects.filter(
        participant=participant, intervention=intervention
    ).first()
    merged = response is not None

    if response is None:
        response = InterventionResponse.objects.create(
            intervention=intervention,
            participant=participant,
            created_by=user,
            client_uuid=client_uuid,
            recorded_at=recorded_at,
            entry_mode=item.get("entry_mode", "live"),
            synced_at=timezone.now(),
        )
        # Only a brand-new record increments the programme's participant count;
        # a merge is the same person being seen again at the same station.
        program = intervention.program
        program.actual_participants = (program.actual_participants or 0) + 1
        program.save(update_fields=["actual_participants"])
    else:
        response.updated_by = user
        response.synced_at = timezone.now()
        # The record's own timestamp tracks the earliest observation.
        if response.recorded_at and recorded_at < response.recorded_at:
            response.recorded_at = recorded_at
        response.save()

    conflicts = _apply_values(response, item.get("answers") or [], recorded_at, user)

    return SyncOutcome(
        client_uuid=client_uuid,
        status="merged" if merged else "created",
        response_id=str(response.id),
        participant_code=participant.participant_code,
        participant_number=participant.participant_number,
        participant_display_code=participant.display_code,
        conflicts=conflicts,
        detail=(
            "Merged into the existing record for this participant."
            if merged
            else "Recorded."
        ),
    )


def sync_batch(organization: Organization, items: List[Dict[str, Any]], user):
    """
    Apply a queue of records.

    Each item is committed independently: one malformed entry from a device
    must not block the rest of a day's work from syncing.
    """
    outcomes = []
    for item in items:
        try:
            outcomes.append(sync_one(organization, item, user))
        except Exception as exc:  # pragma: no cover - defensive
            logger.error(f"Offline sync item failed: {exc}")
            outcomes.append(
                SyncOutcome(
                    client_uuid=str(item.get("client_uuid") or ""),
                    status="failed",
                    detail=str(exc),
                )
            )
    return outcomes
