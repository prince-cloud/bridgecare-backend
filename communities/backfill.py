"""
Give existing participants an event and a number.

`Participant` used to be a person for the whole organisation. It is now a
person at one event, so a row with records in two events must become two rows.
This module does that split and then numbers everyone.

Kept out of the migration file and given model classes as arguments, so it can
be tested as an ordinary function with real models. This follows
`intervention_template_data.py`, which the 0024 migration uses the same way.
"""

from django.db.models import Min
from django.db.models.functions import Coalesce

# The same readable alphabet the model uses. Repeated here rather than imported
# because a migration runs against historical models, which carry no methods
# and no class constants.
CODE_ALPHABET = "ABCDEFGHJKMNPQRTUVWXY346789"
CODE_LENGTH = 4


def _new_code(participant_model, prefix, taken):
    """
    Mint a participant code that nobody holds.

    `taken` is carried across calls so one run does not query the table once
    per clone, and so two clones minted in the same run cannot collide.
    """
    import secrets

    for _ in range(40):
        candidate = prefix + "".join(
            secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH)
        )
        if candidate in taken:
            continue
        if participant_model.objects.filter(participant_code=candidate).exists():
            taken.add(candidate)
            continue
        taken.add(candidate)
        return candidate

    # Widen rather than fail the migration.
    candidate = prefix + "".join(
        secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH + 3)
    )
    taken.add(candidate)
    return candidate


def _first_seen_by_program(response_model):
    """
    Map (program_id, participant_id) to the earliest time that person was
    recorded at that event.

    Orders on `recorded_at`, which is when the measurement was taken, and falls
    back to `date_created`, which is when it was typed. A day of paper slips
    transcribed in the evening shares one `date_created` cluster and keeps the
    real arrival order only in `recorded_at`.
    """
    rows = (
        response_model.objects.filter(
            participant__isnull=False, intervention__isnull=False
        )
        .values("intervention__program_id", "participant_id")
        .annotate(first_seen=Min(Coalesce("recorded_at", "date_created")))
    )

    by_program = {}
    for row in rows:
        program_id = row["intervention__program_id"]
        if program_id is None:
            continue
        by_program.setdefault(program_id, []).append(
            (row["participant_id"], row["first_seen"])
        )
    return by_program


def backfill_participant_numbers(*, participant_model, response_model):
    """
    Split participants across events, then number them.

    Returns (split_count, numbered_count).

    Idempotent. A participant that already carries a programme and a number is
    left alone, so a re-run cannot renumber someone who has already been told
    their number.
    """
    by_program = _first_seen_by_program(response_model)

    # Which events each participant appears at, so we know who must be split.
    programs_by_participant = {}
    for program_id, entries in by_program.items():
        for participant_id, _ in entries:
            programs_by_participant.setdefault(participant_id, []).append(program_id)

    taken_codes = set(
        participant_model.objects.exclude(participant_code=None).values_list(
            "participant_code", flat=True
        )
    )

    split_count = 0
    # Maps (original participant id, program id) to the row that now serves it.
    row_for = {}

    for participant_id, program_ids in programs_by_participant.items():
        original = participant_model.objects.filter(id=participant_id).first()
        if original is None:
            continue

        # Deterministic: the event the person was seen at first keeps the
        # original row, so a re-run makes the same choice.
        ordered = sorted(
            set(program_ids),
            key=lambda pid: min(
                seen for pid_, seen in by_program[pid] if pid_ == participant_id
            ),
        )

        row_for[(participant_id, ordered[0])] = original
        if original.program_id is None:
            original.program_id = ordered[0]
            original.save(update_fields=["program"])

        for program_id in ordered[1:]:
            prefix = "BC"
            if original.organization_id:
                prefix = (
                    getattr(original.organization, "participant_code_prefix", None)
                    or "BC"
                )

            clone = participant_model.objects.create(
                organization_id=original.organization_id,
                program_id=program_id,
                participant_code=_new_code(participant_model, prefix, taken_codes),
                fullname=original.fullname,
                phone_number=original.phone_number,
                email=original.email,
                gender=original.gender,
                date_of_birth=original.date_of_birth,
                age=original.age,
                location=original.location,
            )
            row_for[(participant_id, program_id)] = clone
            split_count += 1

            # Move that event's records onto the clone.
            response_model.objects.filter(
                participant_id=participant_id,
                intervention__program_id=program_id,
            ).update(participant=clone)

    # Number everyone, one event at a time.
    numbered_count = 0
    for program_id, entries in by_program.items():
        # Skip an event that already carries numbers, so a partly applied run
        # resumes instead of colliding.
        if participant_model.objects.filter(
            program_id=program_id, participant_number__isnull=False
        ).exists():
            continue

        # Earliest first, then the id, so ties resolve the same way on every
        # database and a re-run never reshuffles people.
        ordered = sorted(entries, key=lambda pair: (pair[1], str(pair[0])))

        for index, (participant_id, _) in enumerate(ordered, start=1):
            row = row_for.get((participant_id, program_id))
            if row is None:
                continue
            row.participant_number = index
            row.save(update_fields=["participant_number"])
            numbered_count += 1

    return split_count, numbered_count
