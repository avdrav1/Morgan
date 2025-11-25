from celery import Celery
from celery.schedules import crontab
from app.core.config import settings

celery_app = Celery(
    "accountability_assistant",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.scheduler"]
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    # Automatic retry for database connection errors
    task_autoretry_for=(Exception,),  # Retry on any exception
    task_retry_kwargs={'max_retries': 3, 'countdown': 5},  # Retry up to 3 times with 5 second delay
    task_acks_late=True,  # Acknowledge task after completion, not before
    task_reject_on_worker_lost=True,  # Reject task if worker crashes
)

# Periodic task schedule
celery_app.conf.beat_schedule = {
    "process-scheduled-check-ins": {
        "task": "app.tasks.scheduler.process_scheduled_check_ins",
        "schedule": crontab(minute="*/5"),  # Every 5 minutes
    },
    "schedule-upcoming-check-ins": {
        "task": "app.tasks.scheduler.schedule_upcoming_check_ins",
        "schedule": crontab(minute=0, hour="*/6"),  # Every 6 hours
    },
    "detect-and-handle-ghosting": {
        "task": "app.tasks.scheduler.detect_and_handle_ghosting",
        "schedule": crontab(minute=0, hour="*/12"),  # Every 12 hours
    },
    "schedule-blocker-followups": {
        "task": "app.tasks.scheduler.schedule_blocker_followups",
        "schedule": crontab(minute=0, hour="*/4"),  # Every 4 hours
    },
    "send-onboarding-reminders": {
        "task": "app.tasks.scheduler.send_onboarding_reminders",
        "schedule": crontab(minute=0, hour="*/6"),  # Every 6 hours
    },
    "cleanup-abandoned-onboarding-sessions": {
        "task": "app.tasks.scheduler.cleanup_abandoned_onboarding_sessions",
        "schedule": crontab(minute=0, hour=2),  # Daily at 2 AM UTC
    },
}
