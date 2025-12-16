"""Background tasks for Perun's BlackBook."""

from app.tasks.email_sync import scheduler, start_scheduler, stop_scheduler

__all__ = ["scheduler", "start_scheduler", "stop_scheduler"]
