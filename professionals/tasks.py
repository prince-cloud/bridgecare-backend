"""
Scheduled appointment reminders (tech report 18.08.2026, items 3.2 and 4.2).

Celery beat runs `send_appointment_reminders` every 15 minutes. Each run
looks for appointments that start about 24 hours or about 1 hour from now
and have not had that reminder yet. The two `reminder_*_sent_at` fields on
Appointment make a reminder go out once even if a run is repeated.
"""

import logging
from datetime import datetime, timedelta

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from .models import Appointment
from .notifications import send_appointment_reminder

logger = logging.getLogger(__name__)

# The beat interval. A window this wide around each lead time means an
# appointment is picked up by exactly one run, and a missed run (worker
# restart) is caught by the next one because the window slides forward.
RUN_EVERY_MINUTES = 15

# Lead time -> (window start, window end) as offsets from "now". The window
# reaches back one interval so nothing falls between two runs, and reaches
# forward one interval so a slightly late run still qualifies.
LEADS = {
    24: (timedelta(hours=24) - timedelta(minutes=RUN_EVERY_MINUTES), timedelta(hours=24) + timedelta(minutes=RUN_EVERY_MINUTES)),
    1: (timedelta(hours=1) - timedelta(minutes=RUN_EVERY_MINUTES), timedelta(hours=1) + timedelta(minutes=RUN_EVERY_MINUTES)),
}

REMINDABLE_STATUSES = (Appointment.Status.PENDING, Appointment.Status.CONFIRMED)


def _starts_at(appointment):
    naive = datetime.combine(appointment.date, appointment.start_time)
    return timezone.make_aware(naive, timezone.get_current_timezone())


def _due(now, hours_ahead):
    """Appointments whose start falls in the window for this lead time."""
    lo, hi = LEADS[hours_ahead]
    window_start, window_end = now + lo, now + hi
    flag = "reminder_24h_sent_at" if hours_ahead == 24 else "reminder_1h_sent_at"
    # Filter by date first (cheap), then by exact start in Python: the start
    # is date + time in two columns, so the DB cannot compare it directly.
    candidates = (
        Appointment.objects.filter(
            status__in=REMINDABLE_STATUSES,
            date__range=(window_start.date(), window_end.date()),
            **{f"{flag}__isnull": True},
        )
        .select_related("patient__user", "provider__user")
    )
    return [a for a in candidates if window_start <= _starts_at(a) < window_end], flag


@shared_task
def send_appointment_reminders(now=None):
    """Queue the 24-hour and 1-hour reminders that are due. Returns counts."""
    now = now or timezone.now()
    summary = {}
    for hours_ahead in (24, 1):
        due, flag = _due(now, hours_ahead)
        count = 0
        for appointment in due:
            with transaction.atomic():
                # Re-check under lock so two overlapping runs cannot both send.
                locked = (
                    Appointment.objects.select_for_update()
                    .filter(pk=appointment.pk, **{f"{flag}__isnull": True})
                    .first()
                )
                if locked is None:
                    continue
                send_appointment_reminder(appointment, hours_ahead)
                setattr(locked, flag, now)
                locked.save(update_fields=[flag])
                count += 1
        summary[f"{hours_ahead}h"] = count
    logger.info(f"APPOINTMENT_REMINDERS sent={summary}")
    return summary
