"""
Seed the platform-wide intervention templates (13 July 2026 review, item h).

The definitions live in `communities/intervention_template_data.py` so the
data migration that seeds a fresh deployment shares them. Re-running updates
existing platform templates in place and leaves their fields alone, so
adjusting the definitions and re-running with `--reset` is the intended
workflow once Gideon's definitive field list arrives.

    python manage.py seed_intervention_templates
    python manage.py seed_intervention_templates --reset
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from communities.intervention_template_data import seed_platform_templates
from communities.models import (
    InterventionTemplate,
    InterventionTemplateField,
    ProgramInterventionType,
)


class Command(BaseCommand):
    help = "Create or refresh the platform-default intervention templates."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Replace the fields of existing platform templates.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        reset = options["reset"]

        created_count, updated_count = seed_platform_templates(
            template_model=InterventionTemplate,
            template_field_model=InterventionTemplateField,
            intervention_type_model=ProgramInterventionType,
            reset=reset,
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Templates created: {created_count}, updated: {updated_count}"
                + ("" if reset else " (fields left intact; pass --reset to replace)")
            )
        )
