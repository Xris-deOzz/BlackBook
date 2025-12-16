"""
Background email sync task using APScheduler.

Periodically syncs emails from all connected Google accounts.
"""

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import get_settings

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler = AsyncIOScheduler()

# Default sync interval in minutes (can be overridden in settings)
DEFAULT_SYNC_INTERVAL_MINUTES = 15


async def sync_emails_task():
    """
    Background task to sync emails from all connected Google accounts.

    Uses incremental sync for existing accounts, full sync for new ones.
    """
    from app.database import SessionLocal
    from app.models import GoogleAccount
    from app.services.gmail_sync_service import get_gmail_sync_service

    logger.info("Starting scheduled email sync...")

    try:
        with SessionLocal() as db:
            # Get all active accounts
            accounts = db.query(GoogleAccount).filter_by(is_active=True).all()

            if not accounts:
                logger.info("No active Google accounts to sync")
                return

            sync_service = get_gmail_sync_service(db)
            results = sync_service.sync_all_accounts()

            # Log results
            for email, result in results.items():
                if result.success:
                    logger.info(
                        f"Synced {result.messages_synced} messages from {email}"
                    )
                else:
                    logger.error(
                        f"Failed to sync {email}: {result.errors}"
                    )

            logger.info(f"Email sync completed for {len(accounts)} accounts")

    except Exception as e:
        logger.error(f"Email sync task failed: {e}")


def start_scheduler():
    """
    Start the background scheduler.

    Call this from FastAPI startup event.
    """
    settings = get_settings()

    # Get sync interval from settings or use default
    sync_interval = getattr(settings, "email_sync_interval_minutes", DEFAULT_SYNC_INTERVAL_MINUTES)

    # Check if sync is enabled (default to True)
    sync_enabled = getattr(settings, "email_sync_enabled", True)

    if not sync_enabled:
        logger.info("Email sync is disabled in settings")
        return

    # Add the sync job
    scheduler.add_job(
        sync_emails_task,
        trigger=IntervalTrigger(minutes=sync_interval),
        id="email_sync",
        name="Sync emails from Google accounts",
        replace_existing=True,
        next_run_time=datetime.now(timezone.utc),  # Run immediately on startup
    )

    # Start the scheduler
    scheduler.start()
    logger.info(f"Email sync scheduler started (interval: {sync_interval} minutes)")


def stop_scheduler():
    """
    Stop the background scheduler gracefully.

    Call this from FastAPI shutdown event.
    """
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Email sync scheduler stopped")


async def run_sync_now():
    """
    Trigger an immediate sync (for manual sync button).

    Returns dict with results per account.
    """
    from app.database import SessionLocal
    from app.services.gmail_sync_service import get_gmail_sync_service

    with SessionLocal() as db:
        sync_service = get_gmail_sync_service(db)
        return sync_service.sync_all_accounts()
