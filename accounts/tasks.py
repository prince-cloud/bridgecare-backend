from celery import shared_task
from django.conf import settings
import requests
from loguru import logger
from jinja2 import Environment, FileSystemLoader
import os
from typing import Dict


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
    # return ""
    url = "https://apps.mnotify.net/smsapi"
    sender_id = settings.MNOTIFY_SENDER_ID
    api_key = settings.MNOTIFY_API_KEY

    params = {
        "key": api_key,
        "to": to,
        "msg": body,
        "sender_id": sender_id,
    }

    try:
        response = requests.post(url, params=params)
        logger.info(f"Response: {response.text}")
        response.raise_for_status()
        logger.info("Message sent successfully!")
        return response.json()  # Assuming API returns JSON
    except requests.RequestException as e:
        logger.error(f"An error occurred sending otp {e}")
        return {"status": "error", "message": str(e)}
