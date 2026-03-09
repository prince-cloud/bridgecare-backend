import os
from celery import Celery
import logging

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
}


app.autodiscover_tasks()
