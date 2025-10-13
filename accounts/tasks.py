from celery import shared_task
from django.conf import settings
import requests
from loguru import logger
from jinja2 import Environment, FileSystemLoader
import os
from typing import Dict


@shared_task
def generic_send_mail(recipient, title, payload: Dict[str, str] = {}):
    """
    Send generic email using specified template type.

    Args:
        recipient: Email address of the recipient
        title: Email subject
        payload: Dictionary containing template variables
    """
    env = Environment(
        loader=FileSystemLoader(os.path.join(os.path.dirname(__file__), "templates"))
    )

    template_file = "template.html"
    template = env.get_template(template_file)

    # Add current year to payload
    from datetime import datetime

    payload["current_year"] = datetime.now().year

    html_message = template.render(payload)
    logger.info(f"sending email to {recipient}")
    try:
        base_url = "https://0qmusixj1f.execute-api.us-east-1.amazonaws.com/sendEmail"
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
def generic_send_sms(to, body):
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
