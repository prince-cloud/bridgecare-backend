import os
import certifi
from celery import Celery
import logging

# macOS Python 3.14 ships without system CA bundle — point SSL at certifi.
os.environ.setdefault("SSL_CERT_FILE", certifi.where())
os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())

from celery.schedules import crontab


logger = logging.getLogger(__name__)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("aimy-ai")
app.config_from_object("django.conf:settings", namespace="CELERY")

app.conf.beat_schedule = {
    "calculate-daily-pharmacy-settlements": {
        "task": "pharmacies.tasks.calculate_daily_settlements",
        "schedule": crontab(hour=23, minute=55),
    },
    "send-daily-expiry-alerts": {
        "task": "pharmacies.tasks.send_expiry_alerts",
        "schedule": crontab(hour=8, minute=0),
    },
}


app.autodiscover_tasks()

# Python 3.14: fork()-based prefork workers SIGSEGV when C extensions (Pillow,
# ReportLab) are loaded in the parent process. Threads share the same process
# so no fork occurs — this eliminates the crash.
app.conf.worker_pool = "threads"
