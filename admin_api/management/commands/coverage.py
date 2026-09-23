from collections import defaultdict

from django.apps import apps
from django.core.management.base import BaseCommand

from admin_api.coverage import COVERAGE, DONE


class Command(BaseCommand):
    help = "Admin portal coverage: every model → how the portal exposes it."

    def handle(self, *args, **options):
        by_app = defaultdict(list)
        for model in apps.get_models():
            label = f"{model._meta.app_label}.{model._meta.model_name}"
            if label in COVERAGE:
                by_app[model._meta.app_label].append((model._meta.model_name, *COVERAGE[label]))
            else:
                by_app[model._meta.app_label].append((model._meta.model_name, None, None, None))

        total = done = 0
        for app in ["accounts", "communities", "facilities", "professionals", "patients", "pharmacies", "partners", "chat", "public_api"]:
            rows = by_app.get(app, [])
            self.stdout.write(self.style.MIGRATE_HEADING(f"\n{app}"))
            for name, mode, key, phase in rows:
                total += 1
                if mode is None:
                    self.stdout.write(self.style.ERROR(f"  ✗ {name:28s} NOT MAPPED — add to admin_api/coverage.py"))
                    continue
                if key in DONE:
                    done += 1
                    status = self.style.SUCCESS("✓ live")
                else:
                    status = self.style.WARNING(f"… planned Phase {phase}")
                label = f"{mode} → {key}" if mode.startswith("inline") else (key or "—")
                self.stdout.write(f"  {status:12s} {name:28s} {mode:10s} {label}")

        pct = round(100 * done / total) if total else 0
        self.stdout.write(self.style.MIGRATE_HEADING(f"\nCoverage: {done}/{total} models visible ({pct}%)"))
