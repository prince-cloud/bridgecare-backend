"""
Appointment emails (tech report 18.08.2026, items 3.1, 3.2 and 4.2).

- `send_appointment_booked` goes out once, when a patient books.
- `send_appointment_reminder` goes out from the Celery task in `tasks.py`
  about 24 hours and again about 1 hour before the start time.

Each function returns the number of emails queued. Mail is queued with the
Celery task `generic_send_mail`, so a slow provider never delays a request.
Every send is wrapped: a mail failure must not break a booking.
"""

import logging

from django.conf import settings

from accounts.tasks import generic_send_mail

logger = logging.getLogger(__name__)


def _name(user):
    if user is None:
        return ""
    return (user.get_full_name() or "").strip() or user.email or ""


def _when(appointment):
    date = appointment.date.strftime("%A %d %B %Y")
    start = appointment.start_time.strftime("%H:%M")
    end = appointment.end_time.strftime("%H:%M") if appointment.end_time else ""
    return f"{date}, {start}" + (f" – {end}" if end else "")


def _where(appointment):
    if appointment.appointment_type == "TELEHEALTH":
        mode = (appointment.telehealth_mode or "").capitalize()
        return f"Telehealth ({mode})" if mode else "Telehealth"
    return appointment.visitation_location or "In person"


def _queue(recipient, title, body_html, user_name):
    if not recipient:
        return 0
    try:
        generic_send_mail.delay(
            recipient=recipient,
            title=title,
            payload={"user_name": user_name, "body": body_html},
        )
        return 1
    except Exception as exc:  # pragma: no cover - broker down must not break the flow
        logger.error(f"APPOINTMENT_MAIL_NOT_QUEUED to={recipient}: {exc}")
        return 0


def _details_html(appointment, patient_name, provider_name):
    return (
        f"<p><strong>Health professional:</strong> {provider_name}</p>"
        f"<p><strong>Patient:</strong> {patient_name}</p>"
        f"<p><strong>When:</strong> {_when(appointment)}</p>"
        f"<p><strong>Where:</strong> {_where(appointment)}</p>"
        + (f"<p><strong>Reason:</strong> {appointment.reason}</p>" if appointment.reason else "")
    )


def send_appointment_booked(appointment) -> int:
    """Confirmation to the patient and a notice to the professional."""
    patient_user = getattr(appointment.patient, "user", None)
    provider_user = getattr(appointment.provider, "user", None)
    patient_name = _name(patient_user) or "Patient"
    provider_name = _name(provider_user) or "your health professional"
    details = _details_html(appointment, patient_name, provider_name)
    link = f"{settings.FRONTEND_URL}/login"

    sent = 0
    sent += _queue(
        getattr(patient_user, "email", None),
        "Your appointment is booked",
        f"<p>Your appointment request has been sent to {provider_name}. "
        f"You will get another email when it is confirmed.</p>{details}"
        f'<p><a href="{link}">Open BridgeCare One</a> to see or change it.</p>',
        patient_name,
    )
    sent += _queue(
        getattr(provider_user, "email", None),
        f"New appointment request from {patient_name}",
        f"<p>{patient_name} has requested an appointment with you.</p>{details}"
        f'<p><a href="{link}">Open BridgeCare One</a> to confirm or reschedule.</p>',
        provider_name,
    )
    return sent


def send_appointment_reminder(appointment, hours_ahead: int) -> int:
    """Reminder to both parties. `hours_ahead` is 24 or 1."""
    patient_user = getattr(appointment.patient, "user", None)
    provider_user = getattr(appointment.provider, "user", None)
    patient_name = _name(patient_user) or "Patient"
    provider_name = _name(provider_user) or "your health professional"
    details = _details_html(appointment, patient_name, provider_name)
    lead = "tomorrow" if hours_ahead >= 24 else "in about an hour"
    title = f"Reminder: appointment {lead}"

    sent = 0
    sent += _queue(
        getattr(patient_user, "email", None),
        title,
        f"<p>This is a reminder of your appointment with {provider_name} {lead}.</p>{details}",
        patient_name,
    )
    sent += _queue(
        getattr(provider_user, "email", None),
        title,
        f"<p>This is a reminder of your appointment with {patient_name} {lead}.</p>{details}",
        provider_name,
    )
    return sent
