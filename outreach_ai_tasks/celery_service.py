from celery import Celery
from celery.schedules import crontab
import os
import django
from celery.utils.time import timedelta


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "outreach_ai.settings")
django.setup()

celery_app = Celery("outreach_app", broker='redis://localhost:6379/0', backend='redis://localhost:6379/0')

celery_app.conf.update(
    result_backend='redis://localhost:6379/0',
    worker_concurrency=1,
    include=[
        'outreach_ai_tasks.celery_task.tasks','outreach_ai_tasks.user_task.tasks'
    ]
)
#Beat will run after every 24 hours
celery_app.conf.update(
    beat_schedule={
        'email-generation-task': {
            'task': 'schedule_tasks', 
            'schedule':  crontab(hour=12, minute=0),  
            # 'schedule': timedelta(seconds=30), 
        },
    }
)
