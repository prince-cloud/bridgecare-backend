from datetime import datetime, time, timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from accounts.models import CustomUser
from patients.models import PatientProfile
from professionals.models import Appointment, ProfessionalProfile
from professionals.notifications import send_appointment_booked
from professionals.tasks import send_appointment_reminders


def make_pair():
    patient_user = CustomUser.objects.create_user(
        username="pat@example.com",
        email="pat@example.com",
        password="pw-for-tests",
        first_name="Ama",
        last_name="Mensah",
    )
    patient, _ = PatientProfile.objects.get_or_create(user=patient_user)
    doctor_user = CustomUser.objects.create_user(
        username="doc@example.com",
        email="doc@example.com",
        password="pw-for-tests",
        first_name="Kofi",
        last_name="Boateng",
    )
    doctor, _ = ProfessionalProfile.objects.get_or_create(user=doctor_user)
    return patient, doctor


def make_appointment(patient, doctor, starts_at, status=Appointment.Status.CONFIRMED):
    local = timezone.localtime(starts_at)
    return Appointment.objects.create(
        patient=patient,
        provider=doctor,
        date=local.date(),
        start_time=local.time().replace(second=0, microsecond=0),
        end_time=(local + timedelta(hours=1)).time().replace(second=0, microsecond=0),
        appointment_type="IN_PERSON",
        visitation_location="Ridge Hospital",
        reason="Headaches",
        status=status,
    )


class BookingEmailTests(TestCase):
    """Tech report 18.08.2026, item 3.1: confirmation on booking."""

    def setUp(self):
        self.patient, self.doctor = make_pair()

    @patch("professionals.notifications.generic_send_mail")
    def test_booking_mails_patient_and_professional(self, mail):
        appointment = make_appointment(
            self.patient, self.doctor, timezone.now() + timedelta(days=3)
        )
        sent = send_appointment_booked(appointment)

        self.assertEqual(sent, 2)
        recipients = {call.kwargs["recipient"] for call in mail.delay.call_args_list}
        self.assertEqual(recipients, {"pat@example.com", "doc@example.com"})
        patient_mail = next(
            c for c in mail.delay.call_args_list if c.kwargs["recipient"] == "pat@example.com"
        )
        self.assertIn("Kofi Boateng", patient_mail.kwargs["payload"]["body"])
        self.assertIn("Ridge Hospital", patient_mail.kwargs["payload"]["body"])

    @patch("professionals.notifications.generic_send_mail")
    def test_a_broker_failure_does_not_raise(self, mail):
        mail.delay.side_effect = RuntimeError("broker down")
        appointment = make_appointment(
            self.patient, self.doctor, timezone.now() + timedelta(days=3)
        )
        self.assertEqual(send_appointment_booked(appointment), 0)


class ReminderTaskTests(TestCase):
    """Tech report 18.08.2026, items 3.2 and 4.2: 24-hour and 1-hour reminders."""

    def setUp(self):
        self.patient, self.doctor = make_pair()
        # A fixed "now" on a minute boundary keeps the windows predictable.
        self.now = timezone.make_aware(datetime(2026, 9, 23, 9, 0))

    @patch("professionals.notifications.generic_send_mail")
    def test_24h_and_1h_reminders_go_out_once(self, mail):
        in_24h = make_appointment(self.patient, self.doctor, self.now + timedelta(hours=24))
        in_1h = make_appointment(self.patient, self.doctor, self.now + timedelta(hours=1))
        # Outside both windows: nothing should be sent for these.
        make_appointment(self.patient, self.doctor, self.now + timedelta(hours=5))
        make_appointment(self.patient, self.doctor, self.now + timedelta(days=3))

        first = send_appointment_reminders(now=self.now)
        self.assertEqual(first, {"24h": 1, "1h": 1})
        # Two parties per reminder.
        self.assertEqual(mail.delay.call_count, 4)

        in_24h.refresh_from_db()
        in_1h.refresh_from_db()
        self.assertIsNotNone(in_24h.reminder_24h_sent_at)
        self.assertIsNone(in_24h.reminder_1h_sent_at)
        self.assertIsNotNone(in_1h.reminder_1h_sent_at)

        # A repeated run in the same window sends nothing more.
        mail.delay.reset_mock()
        second = send_appointment_reminders(now=self.now + timedelta(minutes=5))
        self.assertEqual(second, {"24h": 0, "1h": 0})
        self.assertEqual(mail.delay.call_count, 0)

    @patch("professionals.notifications.generic_send_mail")
    def test_cancelled_appointments_get_no_reminder(self, mail):
        make_appointment(
            self.patient,
            self.doctor,
            self.now + timedelta(hours=1),
            status=Appointment.Status.CANCELLED,
        )
        self.assertEqual(send_appointment_reminders(now=self.now), {"24h": 0, "1h": 0})
        self.assertEqual(mail.delay.call_count, 0)

    @patch("professionals.notifications.generic_send_mail")
    def test_a_missed_run_is_caught_by_the_next_window(self, mail):
        # Starts 24h10m from now: inside the 24h window (23h45 .. 24h15).
        make_appointment(self.patient, self.doctor, self.now + timedelta(hours=24, minutes=10))
        self.assertEqual(send_appointment_reminders(now=self.now)["24h"], 1)
