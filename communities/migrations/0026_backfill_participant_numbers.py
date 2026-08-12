"""
Give existing participants an event and a number.

`Participant` used to be a person for the whole organisation. It is now a
person at one event. A row with records in two events becomes two rows here,
and everyone is then numbered from the order they were first recorded.

The work lives in `communities/backfill.py` so it can be tested as an ordinary
function. This follows `0024_seed_intervention_templates.py`.
"""

from django.db import migrations

from communities.backfill import backfill_participant_numbers


def backfill(apps, schema_editor):
    backfill_participant_numbers(
        participant_model=apps.get_model("communities", "Participant"),
        response_model=apps.get_model("communities", "InterventionResponse"),
    )


def unbackfill(apps, schema_editor):
    """
    Clear the numbers and the event link.

    The split rows are deliberately left in place. Merging them back would have
    to guess which clone was the original, and deleting them would destroy the
    records that were moved onto them.
    """
    Participant = apps.get_model("communities", "Participant")
    Participant.objects.update(participant_number=None, program=None)


class Migration(migrations.Migration):
    dependencies = [
        ("communities", "0025_participant_participant_number_participant_program_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill, unbackfill),
    ]
