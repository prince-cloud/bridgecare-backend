from celery import shared_task
from django.conf import settings
import requests
from loguru import logger
from jinja2 import Environment, FileSystemLoader
import os
from typing import Dict, Optional
import io


class EmailDeliveryError(Exception):
    """Raised when an outbound email could not be handed off to a mail provider."""


def _render_email(payload: Optional[Dict[str, str]], email_type: Optional[str]) -> str:
    """Render the shared BridgeCare email template."""
    from datetime import datetime

    env = Environment(
        loader=FileSystemLoader(os.path.join(os.path.dirname(__file__), "templates"))
    )
    template = env.get_template("email_template.html")

    # Copy so we never mutate a caller's dict (or a shared default).
    context = dict(payload or {})
    context["current_year"] = datetime.now().year
    context["email_type"] = email_type
    return template.render(context)


def _record_delivery(
    recipient: str, title: str, email_type: Optional[str], provider: str,
    success: bool, error: str = "",
) -> None:
    """
    Persist the outcome of every send attempt so failed deliveries are visible
    without waiting for a user to complain. Never allowed to break a send.
    """
    try:
        from .models import EmailDeliveryLog

        EmailDeliveryLog.objects.create(
            recipient=recipient,
            subject=title[:255],
            email_type=email_type or "",
            provider=provider,
            success=success,
            error=error[:2000],
        )
    except Exception as exc:  # pragma: no cover - logging must never cascade
        logger.warning(f"Could not write EmailDeliveryLog: {exc}")


def _deliver_via_relay(recipient: str, title: str, html_message: str) -> None:
    """Send through the AWS email relay. Raises EmailDeliveryError on failure."""
    base_url = settings.AWS_EMAIL_URL
    try:
        response = requests.post(
            base_url,
            json={"recipient": recipient, "subject": title, "body": html_message},
            headers={"Content-Type": "application/json"},
            timeout=getattr(settings, "EMAIL_RELAY_TIMEOUT", 15),
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise EmailDeliveryError(f"relay request failed: {exc}") from exc


def _deliver_via_smtp(recipient: str, title: str, html_message: str) -> None:
    """Send through Django's configured SMTP backend."""
    from django.core.mail import EmailMessage

    if not settings.EMAIL_HOST and not settings.DEBUG:
        raise EmailDeliveryError("no SMTP host configured and no email relay URL set")

    try:
        msg = EmailMessage(
            subject=title,
            body=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient],
        )
        msg.content_subtype = "html"
        sent = msg.send(fail_silently=False)
    except Exception as exc:
        raise EmailDeliveryError(f"SMTP send failed: {exc}") from exc

    if not sent:
        raise EmailDeliveryError("SMTP backend accepted 0 recipients")


def deliver_email(
    recipient: str,
    title: str,
    payload: Optional[Dict[str, str]] = None,
    email_type: Optional[str] = None,
) -> None:
    """
    Render and send a single transactional email.

    Prefers the AWS relay when `AWS_EMAIL_URL` is configured and falls back to
    Django's SMTP backend otherwise, so a missing relay URL degrades instead of
    silently dropping the message. Raises `EmailDeliveryError` if the message
    could not be handed to any provider.
    """
    if not recipient:
        raise EmailDeliveryError("no recipient supplied")

    html_message = _render_email(payload, email_type)
    relay_url = (getattr(settings, "AWS_EMAIL_URL", "") or "").strip()
    provider = "relay" if relay_url else "smtp"

    logger.info(f"sending '{email_type or 'generic'}' email to {recipient} via {provider}")
    try:
        if relay_url:
            _deliver_via_relay(recipient, title, html_message)
        else:
            _deliver_via_smtp(recipient, title, html_message)
    except EmailDeliveryError as exc:
        # Loud, greppable marker so alerting can key on failed transactional mail.
        logger.error(f"EMAIL_DELIVERY_FAILED type={email_type} to={recipient}: {exc}")
        _record_delivery(recipient, title, email_type, provider, False, str(exc))
        raise

    _record_delivery(recipient, title, email_type, provider, True)


def mail_provider_ready() -> bool:
    """
    Can this environment send mail at all?

    Deliberately account-independent. The password-reset endpoint must give the
    same answer whether or not an address is registered; deciding "is mail
    broken?" from the *result of sending to a specific user* would leak account
    existence whenever the provider is down — reopening the enumeration hole
    that finding 2.1 is about, through the fix for finding 2.2.
    """
    if (getattr(settings, "AWS_EMAIL_URL", "") or "").strip():
        return True
    if settings.EMAIL_HOST:
        return True
    # In DEBUG the console backend always "delivers", which is what developers
    # expect locally.
    return bool(settings.DEBUG)


def send_mail_now(
    recipient: str,
    title: str,
    payload: Optional[Dict[str, str]] = None,
    email_type: Optional[str] = None,
) -> bool:
    """
    Synchronous send for callers that must know the real outcome (e.g. password
    reset, where the UI must not claim success when nothing was sent).

    Returns True only if a provider accepted the message.
    """
    try:
        deliver_email(recipient, title, payload, email_type)
        return True
    except EmailDeliveryError:
        return False


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def generic_send_mail(
    self,
    recipient: str,
    title: str,
    payload: Dict[str, str] = None,
    email_type: str = None,
):
    """
    Send generic email using specified template type with BridgeCare branding.

    Args:
        recipient: Email address of the recipient
        title: Email subject line
        payload: Dictionary containing template variables
        email_type: Type of email for conditional rendering. Supported types:
            - 'otp': OTP verification email (requires 'otp_code' in payload)
            - 'registration': Account registration success email
            - 'login': Login notification email (requires 'login_time', 'device_info', 'location')
            - None or other: Generic email (uses 'body' or 'content' from payload)

    Examples:
        # OTP Email
        generic_send_mail(
            recipient="user@example.com",
            title="OTP for email verification",
            payload={"otp_code": "123456", "user_name": "John Doe"},
            email_type="otp"
        )

        # Registration Email
        generic_send_mail(
            recipient="user@example.com",
            title="Welcome to BridgeCare!",
            payload={"user_name": "John Doe", "login_link": "https://app.bridgecare.com/login"},
            email_type="registration"
        )

        # Login Notification
        generic_send_mail(
            recipient="user@example.com",
            title="New Login to Your BridgeCare Account",
            payload={
                "user_name": "John Doe",
                "login_time": "2025-10-17 10:30 AM",
                "device_info": "Chrome on Windows",
                "location": "Accra, Ghana"
            },
            email_type="login"
        )
    """
    try:
        deliver_email(recipient, title, payload, email_type)
    except EmailDeliveryError as exc:
        # Retry transient provider problems; give up loudly rather than silently.
        if self.request.called_directly:
            raise
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            logger.error(
                f"EMAIL_DELIVERY_ABANDONED type={email_type} to={recipient} "
                f"after {self.max_retries} retries: {exc}"
            )
            return "Mail Failed"
    return "Mail Sent"


@shared_task
def generic_send_sms(to: str, body: str):
    url = f"https://api.mnotify.com/api/sms/quick?key={settings.MNOTIFY_API_KEY}"
    payload = {
        "recipient": [to],
        "sender": settings.MNOTIFY_SENDER_ID,
        "message": body,
        "is_schedule": "False",
        "schedule_date": "",
    }
    try:
        response = requests.post(url, json=payload)
        logger.info(f"mnotify Response: {response.text}")
        response.raise_for_status()
        logger.info("Message sent successfully!")
        return response.json()
    except requests.RequestException as e:
        logger.error(f"An error occurred sending SMS: {e}")
        return {"status": "error", "message": str(e)}


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_certificate_email(self, certificate_id: str, send_email: bool = True,
                            force_resend: bool = False):
    """
    Generate the certificate PDF and optionally email it to the recipient.

    Steps:
      1. Generate PDF via ReportLab/Pillow/pypdf
      2. Save file to media/S3
      3. Send email with PDF attachment via Django SMTP backend
    """
    from django.core.files.base import ContentFile
    from django.core.mail import EmailMessage
    from django.utils import timezone

    try:
        from communities.models import IssuedCertificate
        from communities.certificate_generator import generate_certificate_pdf

        cert = IssuedCertificate.objects.select_related(
            "program", "program__organization", "template", "issued_by"
        ).get(id=certificate_id)

        # Generate PDF
        pdf_bytes = generate_certificate_pdf(cert)

        if not pdf_bytes:
            logger.error(f"Empty PDF for certificate {certificate_id}")
            return

        # Persist file
        filename = f"certificate_{cert.verification_code}.pdf"
        cert.certificate_file.save(filename, ContentFile(pdf_bytes), save=True)

        if not send_email:
            return

        if cert.is_emailed and not force_resend:
            return

        # Build email
        program = cert.program
        org = program.organization
        org_name = org.organization_name if org else "BridgeCare"
        frontend_url = getattr(settings, "FRONTEND_URL", "https://app.bridgecare.com")
        verify_url = f"{frontend_url}/verify/certificate/{cert.verification_code}"

        subject = f"Your Certificate — {program.program_name}"

        from jinja2 import Environment, FileSystemLoader
        from datetime import datetime

        env = Environment(
            loader=FileSystemLoader(os.path.join(os.path.dirname(__file__), "templates"))
        )
        template = env.get_template("email_template.html")
        body_html = template.render(
            email_type="certificate",
            user_name=cert.recipient_name,
            program_name=program.program_name,
            organization_name=org_name,
            verify_url=verify_url,
            verification_code=cert.verification_code,
            current_year=datetime.now().year,
        )

        msg = EmailMessage(
            subject=subject,
            body=body_html,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[cert.recipient_email],
        )
        msg.content_subtype = "html"
        msg.attach(filename, pdf_bytes, "application/pdf")
        msg.send(fail_silently=False)

        cert.is_emailed = True
        cert.emailed_at = timezone.now()
        cert.save(update_fields=["is_emailed", "emailed_at"])
        logger.info(f"Certificate {certificate_id} emailed to {cert.recipient_email}")

    except Exception as exc:
        logger.error(f"Certificate task failed for {certificate_id}: {exc}")
        raise self.retry(exc=exc)
