from celery import shared_task
from django.conf import settings
import requests
from loguru import logger
from jinja2 import Environment, FileSystemLoader
import os
from typing import Dict
import io


@shared_task
def generic_send_mail(
    recipient: str, title: str, payload: Dict[str, str] = {}, email_type: str = None
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
    env = Environment(
        loader=FileSystemLoader(os.path.join(os.path.dirname(__file__), "templates"))
    )

    template_file = "email_template.html"
    template = env.get_template(template_file)

    # Add current year to payload
    from datetime import datetime

    payload["current_year"] = datetime.now().year
    payload["email_type"] = email_type

    html_message = template.render(payload)
    logger.info(f"sending email to {recipient}")
    try:
        base_url = settings.AWS_EMAIL_URL
        body = {
            "recipient": recipient,
            "subject": title,
            "body": html_message,
        }
        email_send = requests.post(
            base_url, json=body, headers={"Content-Type": "application/json"}
        )
        print("== response: ", email_send.text)
        return "Mail Sent"
    except Exception as e:
        logger.warning(f"An error occurred sending email {str(e)}")


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
