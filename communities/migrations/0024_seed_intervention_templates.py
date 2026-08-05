"""
Seed the platform-default intervention templates on deploy.

Deployment runs `manage.py migrate` (see docker-compose) but not the seeding
command, so a fresh test or production database came up with no templates and
organisers were handed an empty form. Doing it here rather than appending to
the compose command means every path that migrates gets them — Docker, CI, or
a manual deploy — and it happens once instead of on every restart.

Idempotent by construction: the shared seeder gets-or-creates by name and
leaves the fields of existing templates alone, so re-running (or a squashed
re-apply) cannot disturb templates organisers are already using.
"""

from django.db import migrations

from communities.intervention_template_data import seed_platform_templates


def seed(apps, schema_editor):
    seed_platform_templates(
        template_model=apps.get_model("communities", "InterventionTemplate"),
        template_field_model=apps.get_model(
            "communities", "InterventionTemplateField"
        ),
        intervention_type_model=apps.get_model(
            "communities", "ProgramInterventionType"
        ),
    )


def unseed(apps, schema_editor):
    """
    Remove the platform defaults, leaving organisation-owned templates alone.

    Nothing records whether a default has since been edited, so reversing this
    drops all of them — including any an operator adjusted in place. Interventions
    already created from a template keep their own copied fields, so live events
    are unaffected; only the reusable starting points go.
    """
    InterventionTemplate = apps.get_model("communities", "InterventionTemplate")
    InterventionTemplate.objects.filter(
        is_platform_default=True, organization__isnull=True
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("communities", "0023_programintervention_title"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
