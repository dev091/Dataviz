import os

from celery import Celery

from worker.tasks import run_due_alerts, run_due_reports, run_due_sync_jobs, run_proactive_insights


redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
result_backend = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

celery_app = Celery("analytics_worker", broker=redis_url, backend=result_backend)
celery_app.conf.timezone = "UTC"
celery_app.conf.beat_schedule = {
    "run-sync-jobs-every-minute": {
        "task": "worker.tasks.run_due_sync_jobs",
        "schedule": 60.0,
    },
    "run-alerts-every-5-min": {
        "task": "worker.tasks.run_due_alerts",
        "schedule": 300.0,
    },
    "run-reports-every-5-min": {
        "task": "worker.tasks.run_due_reports",
        "schedule": 300.0,
    },
    "run-proactive-insights-hourly": {
        "task": "worker.tasks.run_proactive_insights",
        "schedule": 3600.0,
    },
}

celery_app.task(name="worker.tasks.run_due_sync_jobs")(run_due_sync_jobs)
celery_app.task(name="worker.tasks.run_due_alerts")(run_due_alerts)
celery_app.task(name="worker.tasks.run_due_reports")(run_due_reports)
celery_app.task(name="worker.tasks.run_proactive_insights")(run_proactive_insights)
