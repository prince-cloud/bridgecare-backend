"""
Re-render stored certificate PDFs from current data and design.

The PDF is written once — by the issuance task — and then served from storage
forever: the public download view only generates when `certificate_file` is
empty. So a change to the certificate design (or an organisation uploading its
logo after certificates were issued) never reaches certificates that already
exist. This command re-renders them.

Only the rendered file changes. `verification_code` and `verification_hash`
are left untouched, so every certificate already in someone's hands still
verifies against the same code.
"""

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError

from communities.certificate_generator import generate_certificate_pdf
from communities.models import IssuedCertificate


class Command(BaseCommand):
    help = "Re-render stored certificate PDFs (verification codes are unchanged)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--code",
            help="Re-render one certificate by its verification code.",
        )
        parser.add_argument(
            "--organization",
            help="Re-render every certificate issued by organisations whose "
            "name contains this text.",
        )
        parser.add_argument(
            "--program",
            help="Re-render every certificate for this programme id.",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Re-render every certificate on the platform.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would change without writing anything.",
        )

    def handle(self, *args, **options):
        queryset = IssuedCertificate.objects.select_related(
            "program", "program__organization", "template", "issued_by"
        )

        if options["code"]:
            queryset = queryset.filter(verification_code=options["code"])
        elif options["program"]:
            queryset = queryset.filter(program_id=options["program"])
        elif options["organization"]:
            queryset = queryset.filter(
                program__organization__organization_name__icontains=options[
                    "organization"
                ]
            )
        elif not options["all"]:
            # Re-rendering everything by accident is slow and rewrites files
            # for every organisation, so the broad case must be asked for.
            raise CommandError(
                "Narrow it down with --code, --program or --organization, "
                "or pass --all to re-render every certificate."
            )

        total = queryset.count()
        if not total:
            self.stdout.write(self.style.WARNING("No certificates matched."))
            return

        dry_run = options["dry_run"]
        self.stdout.write(
            f"{'Would re-render' if dry_run else 'Re-rendering'} {total} "
            f"certificate{'' if total == 1 else 's'}…"
        )

        rendered = failed = 0
        for cert in queryset.iterator():
            org = cert.program.organization if cert.program else None
            label = f"{cert.verification_code} · {cert.recipient_name}"

            try:
                pdf_bytes = generate_certificate_pdf(cert)
            except Exception as exc:
                # One bad certificate must not abandon the rest of the batch.
                failed += 1
                self.stderr.write(self.style.ERROR(f"  {label}: {exc}"))
                continue

            if not pdf_bytes:
                failed += 1
                self.stderr.write(self.style.ERROR(f"  {label}: empty PDF"))
                continue

            has_logo = bool(org and org.orgnaization_logo)
            note = "with organisation logo" if has_logo else "platform logo only"

            if dry_run:
                self.stdout.write(f"  {label} — {len(pdf_bytes)} bytes, {note}")
            else:
                cert.certificate_file.save(
                    f"certificate_{cert.verification_code}.pdf",
                    ContentFile(pdf_bytes),
                    save=True,
                )
                self.stdout.write(self.style.SUCCESS(f"  {label} — {note}"))
            rendered += 1

        summary = (
            f"{rendered} {'would be re-rendered' if dry_run else 're-rendered'}"
            f"{f', {failed} failed' if failed else ''}."
        )
        self.stdout.write(self.style.SUCCESS(summary))
