"""
Calendar router for Google Calendar integration.

Provides endpoints for viewing calendar events and creating interactions from meetings.
"""

from datetime import datetime, timezone, timedelta, date
from typing import Optional
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import CalendarEvent, Interaction, InteractionMedium, CalendarSettings
from app.services.calendar_service import (
    CalendarService,
    CalendarServiceError,
    CalendarAuthError,
    CalendarAPIError,
    get_calendar_service,
)


class EventCreate(BaseModel):
    """Request model for creating a new calendar event."""
    title: str
    date: str  # Format: YYYY-MM-DD
    start_time: str  # Format: HH:MM (24-hour)
    end_time: Optional[str] = None  # Format: HH:MM (24-hour)
    timezone: Optional[str] = None  # IANA timezone (e.g., "America/New_York")
    description: Optional[str] = None
    location: Optional[str] = None
    guests: Optional[list[str]] = None  # List of email addresses
    add_video_conferencing: bool = False  # Add Google Meet
    notification_minutes: Optional[int] = None  # Reminder in minutes before event
    account_id: Optional[str] = None  # Google account UUID
    recurrence: Optional[str] = None  # RRULE string for recurring events
    color: Optional[str] = None  # Event color (tomato, flamingo, tangerine, banana, sage, basil, peacock, blueberry, lavender, grape, graphite)


class EventUpdate(BaseModel):
    """Request model for updating an existing calendar event."""
    title: Optional[str] = None
    date: Optional[str] = None  # Format: YYYY-MM-DD
    start_time: Optional[str] = None  # Format: HH:MM (24-hour)
    end_time: Optional[str] = None  # Format: HH:MM (24-hour)
    timezone: Optional[str] = None  # IANA timezone
    description: Optional[str] = None
    location: Optional[str] = None
    guests: Optional[list[str]] = None  # List of email addresses (replaces existing)
    add_video_conferencing: bool = False  # Add Google Meet if not present
    recurrence: Optional[str] = None  # RRULE string for recurring events
    account_id: str  # Required: Google account UUID that owns this event
    color: Optional[str] = None  # Event color (tomato, flamingo, tangerine, banana, sage, basil, peacock, blueberry, lavender, grape, graphite)


class EventMove(BaseModel):
    """Request model for moving/rescheduling an event via drag-drop."""
    account_id: str  # Required: Google account UUID
    date: str  # Format: YYYY-MM-DD
    start_time: str  # Format: HH:MM (24-hour)
    end_time: str  # Format: HH:MM (24-hour)

router = APIRouter(prefix="/calendar", tags=["calendar"])
templates = Jinja2Templates(directory="app/templates")

# Default timezone (fallback if settings not available)
DEFAULT_TIMEZONE = "America/New_York"


def get_local_timezone(db: Session) -> ZoneInfo:
    """Get the configured local timezone from settings."""
    settings = CalendarSettings.get_settings(db)
    return ZoneInfo(settings.timezone)


def add_local_times(event: CalendarEvent, local_tz: ZoneInfo) -> CalendarEvent:
    """Add local time properties to a calendar event."""
    if event.start_time:
        event.start_time_local = event.start_time.astimezone(local_tz)
    else:
        event.start_time_local = None
    if event.end_time:
        event.end_time_local = event.end_time.astimezone(local_tz)
    else:
        event.end_time_local = None
    return event


def get_today_tomorrow_local(local_tz: ZoneInfo) -> tuple[date, date]:
    """Get today and tomorrow dates in local timezone."""
    now_local = datetime.now(local_tz)
    today = now_local.date()
    tomorrow = today + timedelta(days=1)
    return today, tomorrow


@router.get("/today", response_class=HTMLResponse)
async def get_todays_events(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Get today's calendar events with attendee information.

    Returns HTML partial for HTMX.
    """
    calendar_service = get_calendar_service(db)
    local_tz = get_local_timezone(db)
    today, tomorrow = get_today_tomorrow_local(local_tz)

    try:
        events = calendar_service.get_todays_events(local_tz=local_tz)

        # Enrich events with matched attendees and local times
        enriched_events = []
        for event in events:
            add_local_times(event, local_tz)
            matched_attendees = calendar_service.match_attendees_to_persons(event)
            enriched_events.append({
                "event": event,
                "attendees": matched_attendees,
                "known_count": len([a for a in matched_attendees if a["person_id"]]),
                "unknown_count": len([a for a in matched_attendees if not a["person_id"]]),
            })

        return templates.TemplateResponse(
            request,
            "calendar/_event_list.html",
            {
                "events": enriched_events,
                "title": "Today's Meetings",
                "empty_message": "No meetings scheduled for today.",
                "today": today,
                "tomorrow": tomorrow,
            },
        )
    except (CalendarAuthError, CalendarAPIError) as e:
        return templates.TemplateResponse(
            request,
            "calendar/_event_list.html",
            {
                "events": [],
                "title": "Today's Meetings",
                "error": str(e),
                "today": today,
                "tomorrow": tomorrow,
            },
        )


@router.get("/upcoming", response_class=HTMLResponse)
async def get_upcoming_events(
    request: Request,
    days: int = 7,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """
    Get upcoming calendar events for the next N days.

    Args:
        days: Number of days to look ahead (default 7)
        offset: Number of days from today to start (default 0)

    Returns HTML partial for HTMX.
    """
    calendar_service = get_calendar_service(db)
    local_tz = get_local_timezone(db)
    today, tomorrow = get_today_tomorrow_local(local_tz)

    try:
        events = calendar_service.get_upcoming_events(days=days, offset=offset)

        # Enrich events with matched attendees and local times
        enriched_events = []
        for event in events:
            add_local_times(event, local_tz)
            matched_attendees = calendar_service.match_attendees_to_persons(event)
            enriched_events.append({
                "event": event,
                "attendees": matched_attendees,
                "known_count": len([a for a in matched_attendees if a["person_id"]]),
                "unknown_count": len([a for a in matched_attendees if not a["person_id"]]),
            })

        return templates.TemplateResponse(
            request,
            "calendar/_event_list.html",
            {
                "events": enriched_events,
                "title": f"Upcoming Meetings ({days} days)",
                "empty_message": "No upcoming meetings scheduled.",
                "today": today,
                "tomorrow": tomorrow,
            },
        )
    except (CalendarAuthError, CalendarAPIError) as e:
        return templates.TemplateResponse(
            request,
            "calendar/_event_list.html",
            {
                "events": [],
                "title": f"Upcoming Meetings ({days} days)",
                "error": str(e),
                "today": today,
                "tomorrow": tomorrow,
            },
        )


@router.get("/event/{event_id}", response_class=HTMLResponse)
async def get_event_details(
    request: Request,
    event_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Get detailed information about a specific calendar event.

    Returns HTML partial with event details and matched persons.
    """
    event = db.query(CalendarEvent).filter_by(id=event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    calendar_service = get_calendar_service(db)
    matched_attendees = calendar_service.match_attendees_to_persons(event)

    return templates.TemplateResponse(
        request,
        "calendar/_event_detail.html",
        {
            "event": event,
            "attendees": matched_attendees,
        },
    )


@router.post("/event/{event_id}/log")
async def log_meeting_as_interaction(
    event_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Create interactions from a calendar meeting.

    Creates one interaction for each matched attendee (person in the database).

    Returns:
        JSON with created interaction count
    """
    event = db.query(CalendarEvent).filter_by(id=event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    calendar_service = get_calendar_service(db)
    matched_attendees = calendar_service.match_attendees_to_persons(event)

    # Determine interaction medium
    medium = InteractionMedium.video_call if event.is_video_call else InteractionMedium.meeting

    created_count = 0
    for attendee in matched_attendees:
        if not attendee["person_id"]:
            continue

        person_id = UUID(attendee["person_id"])

        # Check if interaction already exists for this event+person
        existing = (
            db.query(Interaction)
            .filter_by(
                person_id=person_id,
                calendar_event_id=event.google_event_id,
            )
            .first()
        )
        if existing:
            continue

        # Create interaction
        interaction = Interaction(
            person_id=person_id,
            medium=medium,
            interaction_date=event.start_time,
            notes=event.summary or "Calendar meeting",
            calendar_event_id=event.google_event_id,
            source="calendar",
        )
        db.add(interaction)
        created_count += 1

    db.commit()

    return {
        "success": True,
        "interactions_created": created_count,
        "event_summary": event.summary,
    }


@router.post("/sync", response_class=HTMLResponse)
async def sync_calendar_events(
    request: Request,
    days: int = 30,
    db: Session = Depends(get_db),
):
    """
    Trigger manual sync of past calendar events.

    Fetches events from the past N days and creates pending contacts
    for unknown attendees.

    Args:
        days: Number of days to look back (default 30)

    Returns:
        HTML partial with sync result
    """
    calendar_service = get_calendar_service(db)

    try:
        stats = calendar_service.sync_past_events(days=days)
        return templates.TemplateResponse(
            "calendar/_sync_result.html",
            {
                "request": request,
                "success": True,
                "events_synced": stats.get("events_synced", 0),
                "pending_created": stats.get("pending_contacts_created", 0),
            },
        )
    except CalendarServiceError as e:
        return templates.TemplateResponse(
            "calendar/_sync_result.html",
            {
                "request": request,
                "success": False,
                "message": str(e),
            },
        )


@router.post("/full-sync")
async def full_sync_calendar(
    days: int = 30,
    auto_create_interactions: bool = True,
    db: Session = Depends(get_db),
):
    """
    Perform a full calendar sync with automatic interaction creation.

    This endpoint:
    1. Fetches events from the past N days
    2. Creates pending contacts for unknown attendees
    3. Optionally creates interactions for known attendees

    Args:
        days: Number of days to look back (default 30)
        auto_create_interactions: Whether to auto-create interactions (default True)

    Returns:
        JSON with full sync statistics
    """
    calendar_service = get_calendar_service(db)

    try:
        if auto_create_interactions:
            stats = calendar_service.full_sync(days=days)
        else:
            stats = calendar_service.sync_past_events(days=days)
            stats["events_processed"] = 0
            stats["interactions_created"] = 0

        return {
            "success": True,
            **stats,
        }
    except CalendarServiceError as e:
        return {
            "success": False,
            "error": str(e),
        }


@router.post("/auto-interactions")
async def create_auto_interactions(
    days: int = 30,
    db: Session = Depends(get_db),
):
    """
    Create interactions automatically for past calendar events.

    Only creates interactions for events with attendees who are already
    in the database as persons.

    Args:
        days: Number of days to look back (default 30)

    Returns:
        JSON with creation statistics
    """
    calendar_service = get_calendar_service(db)

    try:
        stats = calendar_service.auto_create_interactions(days=days)
        return {
            "success": True,
            **stats,
        }
    except CalendarServiceError as e:
        return {
            "success": False,
            "error": str(e),
        }


@router.post("/create")
async def create_calendar_event(
    event_create: EventCreate,
    db: Session = Depends(get_db),
):
    """
    Create a new event in Google Calendar.

    Args:
        event_create: Event creation data (title, date, start_time, end_time, description, account_id)

    Returns:
        JSON response with success status and created event ID
    """
    try:
        calendar_service = get_calendar_service(db)

        # Use provided timezone or fall back to user's settings
        event_timezone = event_create.timezone or CalendarSettings.get_timezone(db)

        # Parse date and times
        event_date = datetime.strptime(event_create.date, "%Y-%m-%d").date()

        # Parse start time
        start_hour, start_minute = map(int, event_create.start_time.split(":"))
        start_datetime = datetime(
            event_date.year, event_date.month, event_date.day,
            start_hour, start_minute
        )

        # Parse end time (default to 1 hour after start)
        if event_create.end_time:
            end_hour, end_minute = map(int, event_create.end_time.split(":"))
            end_datetime = datetime(
                event_date.year, event_date.month, event_date.day,
                end_hour, end_minute
            )
            # Handle case where end time is on the next day (e.g., 23:00 - 01:00)
            if end_datetime <= start_datetime:
                end_datetime = end_datetime + timedelta(days=1)
        else:
            end_datetime = start_datetime + timedelta(hours=1)

        # Parse account_id if provided
        account_id = None
        if event_create.account_id:
            try:
                account_id = UUID(event_create.account_id)
            except ValueError:
                pass

        # Create the event
        event_id = calendar_service.create_event(
            summary=event_create.title,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            description=event_create.description,
            location=event_create.location,
            attendee_emails=event_create.guests,
            add_video_conferencing=event_create.add_video_conferencing,
            notification_minutes=event_create.notification_minutes,
            account_id=account_id,
            timezone_str=event_timezone,
            recurrence=event_create.recurrence,
            color=event_create.color,
        )

        if event_id:
            return JSONResponse(
                content={
                    "success": True,
                    "event_id": event_id,
                    "message": "Event created successfully",
                },
                status_code=201,
            )
        else:
            return JSONResponse(
                content={"success": False, "error": "Failed to create event"},
                status_code=400,
            )

    except CalendarServiceError as e:
        return JSONResponse(
            content={"success": False, "error": str(e)},
            status_code=400,
        )
    except Exception as e:
        return JSONResponse(
            content={"success": False, "error": str(e)},
            status_code=500,
        )


@router.put("/update/{google_event_id}")
async def update_calendar_event(
    google_event_id: str,
    event_update: EventUpdate,
    db: Session = Depends(get_db),
):
    """
    Update an existing event in Google Calendar.

    Args:
        google_event_id: The Google Calendar event ID to update
        event_update: Event update data

    Returns:
        JSON response with success status
    """
    try:
        calendar_service = get_calendar_service(db)

        # Parse account_id (required for update)
        try:
            account_id = UUID(event_update.account_id)
        except ValueError:
            return JSONResponse(
                content={"success": False, "error": "Invalid account ID"},
                status_code=400,
            )

        # Use provided timezone or fall back to user's settings
        event_timezone = event_update.timezone or CalendarSettings.get_timezone(db)

        # Parse date and times if provided
        start_datetime = None
        end_datetime = None

        if event_update.date and event_update.start_time:
            event_date = datetime.strptime(event_update.date, "%Y-%m-%d").date()
            start_hour, start_minute = map(int, event_update.start_time.split(":"))
            start_datetime = datetime(
                event_date.year, event_date.month, event_date.day,
                start_hour, start_minute
            )

            if event_update.end_time:
                end_hour, end_minute = map(int, event_update.end_time.split(":"))
                end_datetime = datetime(
                    event_date.year, event_date.month, event_date.day,
                    end_hour, end_minute
                )
                # Handle case where end time is on the next day
                if end_datetime <= start_datetime:
                    end_datetime = end_datetime + timedelta(days=1)
            else:
                end_datetime = start_datetime + timedelta(hours=1)

        # Update the event
        updated = calendar_service.update_event(
            google_event_id=google_event_id,
            account_id=account_id,
            summary=event_update.title,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            description=event_update.description,
            location=event_update.location,
            attendee_emails=event_update.guests,
            add_video_conferencing=event_update.add_video_conferencing,
            timezone_str=event_timezone,
            recurrence=event_update.recurrence,
            color=event_update.color,
        )

        if updated:
            return JSONResponse(
                content={
                    "success": True,
                    "event_id": google_event_id,
                    "message": "Event updated successfully",
                },
                status_code=200,
            )
        else:
            return JSONResponse(
                content={"success": False, "error": "Failed to update event"},
                status_code=400,
            )

    except CalendarServiceError as e:
        return JSONResponse(
            content={"success": False, "error": str(e)},
            status_code=400,
        )
    except Exception as e:
        return JSONResponse(
            content={"success": False, "error": str(e)},
            status_code=500,
        )


@router.post("/event/{google_event_id}/move")
async def move_calendar_event(
    google_event_id: str,
    event_move: EventMove,
    db: Session = Depends(get_db),
):
    """
    Move/reschedule an event via drag-drop in the calendar.

    This is a simplified endpoint for calendar drag-drop operations.

    Args:
        google_event_id: The Google Calendar event ID to move
        event_move: New date, start time, and end time

    Returns:
        JSON response with success status
    """
    try:
        calendar_service = get_calendar_service(db)

        # Parse account_id
        try:
            account_id = UUID(event_move.account_id)
        except ValueError:
            return JSONResponse(
                content={"success": False, "error": "Invalid account ID"},
                status_code=400,
            )

        # Use user's timezone from settings
        event_timezone = CalendarSettings.get_timezone(db)

        # Parse date and times
        event_date = datetime.strptime(event_move.date, "%Y-%m-%d").date()
        start_hour, start_minute = map(int, event_move.start_time.split(":"))
        end_hour, end_minute = map(int, event_move.end_time.split(":"))

        start_datetime = datetime(
            event_date.year, event_date.month, event_date.day,
            start_hour, start_minute
        )
        end_datetime = datetime(
            event_date.year, event_date.month, event_date.day,
            end_hour, end_minute
        )

        # Handle case where end time is on the next day
        if end_datetime <= start_datetime:
            end_datetime = end_datetime + timedelta(days=1)

        # Update the event
        updated = calendar_service.update_event(
            google_event_id=google_event_id,
            account_id=account_id,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            timezone_str=event_timezone,
        )

        if updated:
            return JSONResponse(
                content={
                    "success": True,
                    "event_id": google_event_id,
                    "message": "Event moved successfully",
                },
                status_code=200,
            )
        else:
            return JSONResponse(
                content={"success": False, "error": "Failed to move event"},
                status_code=400,
            )

    except CalendarServiceError as e:
        return JSONResponse(
            content={"success": False, "error": str(e)},
            status_code=400,
        )
    except Exception as e:
        return JSONResponse(
            content={"success": False, "error": str(e)},
            status_code=500,
        )


@router.get("/week-view", response_class=HTMLResponse)
async def get_week_view(
    request: Request,
    days: int = 5,
    account_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Get a week/multi-day column view of upcoming events.

    Shows events in columns (one per day) like Google Calendar's week view.

    Args:
        days: Number of days to show (default 5)
        account_id: Optional UUID string to filter events to a specific Google account.
    """
    import calendar as cal_module

    calendar_service = get_calendar_service(db)
    local_tz = get_local_timezone(db)
    today_local = datetime.now(local_tz).date()

    # Parse account_id if provided
    selected_account_id = None
    if account_id and account_id.strip():
        try:
            selected_account_id = UUID(account_id)
        except ValueError:
            pass

    try:
        # Get events for the next N days starting from tomorrow
        events = calendar_service.get_upcoming_events(days=days, offset=1, account_id=selected_account_id)

        # Group events by date
        events_by_date = {}
        for i in range(days):
            event_date = today_local + timedelta(days=i + 1)
            events_by_date[event_date] = []

        for event in events:
            add_local_times(event, local_tz)
            if event.start_time_local:
                event_date = event.start_time_local.date()
                if event_date in events_by_date:
                    matched_attendees = calendar_service.match_attendees_to_persons(event)
                    events_by_date[event_date].append({
                        "event": event,
                        "attendees": matched_attendees,
                        "known_count": len([a for a in matched_attendees if a["person_id"]]),
                    })

        # Build day columns data
        day_columns = []
        for i in range(days):
            event_date = today_local + timedelta(days=i + 1)
            day_columns.append({
                "date": event_date,
                "day_name": cal_module.day_abbr[event_date.weekday()],
                "day_num": event_date.day,
                "month_name": cal_module.month_abbr[event_date.month],
                "is_today": event_date == today_local,
                "events": events_by_date.get(event_date, []),
            })

        return templates.TemplateResponse(
            request,
            "calendar/_week_view.html",
            {
                "day_columns": day_columns,
                "today": today_local,
            },
        )
    except (CalendarAuthError, CalendarAPIError) as e:
        return templates.TemplateResponse(
            request,
            "calendar/_week_view.html",
            {
                "day_columns": [],
                "error": str(e),
                "today": today_local,
            },
        )


@router.get("/month-view", response_class=HTMLResponse)
async def get_month_view(
    request: Request,
    month: int | None = None,
    year: int | None = None,
    db: Session = Depends(get_db),
):
    """
    Get a monthly calendar view of events.

    Shows events in a monthly grid like Google Calendar's month view.

    Args:
        month: Month number (1-12), defaults to current month
        year: Year, defaults to current year
    """
    import calendar as cal_module

    calendar_service = get_calendar_service(db)
    local_tz = get_local_timezone(db)
    today_local = datetime.now(local_tz).date()

    # Default to current month/year
    display_year = year if year else today_local.year
    display_month = month if month else today_local.month

    # Calculate first and last day of the month
    first_day = date(display_year, display_month, 1)
    if display_month == 12:
        last_day = date(display_year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = date(display_year, display_month + 1, 1) - timedelta(days=1)

    # Calculate days to fetch (include some buffer for the calendar grid)
    days_in_month = (last_day - first_day).days + 1

    try:
        # Calculate offset from today to first of month
        offset_from_today = (first_day - today_local).days
        if offset_from_today < 0:
            # First of month is in the past, fetch from today
            fetch_offset = 0
            fetch_days = (last_day - today_local).days + 1
        else:
            fetch_offset = offset_from_today
            fetch_days = days_in_month

        # Fetch events for the month
        events = calendar_service.get_upcoming_events(days=max(fetch_days, 1), offset=max(fetch_offset, 0))

        # Group events by date
        events_by_date = {}
        for event in events:
            add_local_times(event, local_tz)
            if event.start_time_local:
                event_date = event.start_time_local.date()
                if first_day <= event_date <= last_day:
                    if event_date not in events_by_date:
                        events_by_date[event_date] = []
                    events_by_date[event_date].append({
                        "event": event,
                        "is_all_day": event.is_all_day,
                    })

        # Generate calendar grid (weeks)
        cal = cal_module.Calendar(firstweekday=6)  # Start on Sunday
        month_weeks = cal.monthdayscalendar(display_year, display_month)

        # Build week data with events
        weeks_data = []
        for week in month_weeks:
            week_data = []
            for day in week:
                if day == 0:
                    week_data.append({"day": 0, "events": [], "is_today": False})
                else:
                    day_date = date(display_year, display_month, day)
                    week_data.append({
                        "day": day,
                        "date": day_date,
                        "events": events_by_date.get(day_date, []),
                        "is_today": day_date == today_local,
                        "is_past": day_date < today_local,
                    })
            weeks_data.append(week_data)

        # Calculate prev/next month
        if display_month == 1:
            prev_month, prev_year = 12, display_year - 1
        else:
            prev_month, prev_year = display_month - 1, display_year

        if display_month == 12:
            next_month, next_year = 1, display_year + 1
        else:
            next_month, next_year = display_month + 1, display_year

        return templates.TemplateResponse(
            request,
            "calendar/_month_view.html",
            {
                "weeks": weeks_data,
                "month_name": cal_module.month_name[display_month],
                "year": display_year,
                "month": display_month,
                "today": today_local,
                "prev_month": prev_month,
                "prev_year": prev_year,
                "next_month": next_month,
                "next_year": next_year,
            },
        )
    except (CalendarAuthError, CalendarAPIError) as e:
        return templates.TemplateResponse(
            request,
            "calendar/_month_view.html",
            {
                "weeks": [],
                "error": str(e),
                "month_name": cal_module.month_name[display_month],
                "year": display_year,
                "month": display_month,
                "today": today_local,
            },
        )


@router.get("/api/today")
async def api_get_todays_events(
    db: Session = Depends(get_db),
):
    """
    API endpoint: Get today's calendar events as JSON.

    Returns list of events with matched attendees.
    """
    calendar_service = get_calendar_service(db)
    local_tz = get_local_timezone(db)

    try:
        events = calendar_service.get_todays_events(local_tz=local_tz)

        result = []
        for event in events:
            matched_attendees = calendar_service.match_attendees_to_persons(event)
            result.append({
                "id": str(event.id),
                "google_event_id": event.google_event_id,
                "summary": event.summary,
                "start_time": event.start_time.isoformat() if event.start_time else None,
                "end_time": event.end_time.isoformat() if event.end_time else None,
                "location": event.location,
                "is_video_call": event.is_video_call,
                "duration_minutes": event.duration_minutes,
                "attendees": matched_attendees,
            })

        return {"events": result}
    except CalendarServiceError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/upcoming")
async def api_get_upcoming_events(
    days: int = 7,
    db: Session = Depends(get_db),
):
    """
    API endpoint: Get upcoming calendar events as JSON.

    Args:
        days: Number of days to look ahead (default 7)
    """
    calendar_service = get_calendar_service(db)

    try:
        events = calendar_service.get_upcoming_events(days=days)

        result = []
        for event in events:
            matched_attendees = calendar_service.match_attendees_to_persons(event)
            result.append({
                "id": str(event.id),
                "google_event_id": event.google_event_id,
                "summary": event.summary,
                "start_time": event.start_time.isoformat() if event.start_time else None,
                "end_time": event.end_time.isoformat() if event.end_time else None,
                "location": event.location,
                "is_video_call": event.is_video_call,
                "duration_minutes": event.duration_minutes,
                "attendees": matched_attendees,
            })

        return {"events": result}
    except CalendarServiceError as e:
        raise HTTPException(status_code=500, detail=str(e))
