"""
Dashboard router for widget endpoints.

Provides HTMX endpoints for dashboard widgets including:
- Mini calendar with month navigation
- Today's schedule (timed events)
- Birthday reminders (compact and full views)
- Tasks panel with date filtering (today/tomorrow/week)
- Tasks kanban view (all lists)
- Dashboard layout management
"""

import calendar
import json
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import extract, or_
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Person, GoogleAccount, Setting, PersonEmail, CalendarEvent


class DashboardLayoutUpdate(BaseModel):
    """Request model for updating dashboard layout."""
    section_order: list[str]

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
templates = Jinja2Templates(directory="app/templates")


def get_upcoming_birthdays(db: Session, days: int = 30) -> list[dict]:
    """
    Get upcoming birthdays within the next N days.

    Returns a list of birthday data dictionaries sorted by days until birthday.
    """
    today = date.today()

    # Get all people with birthdays
    people_with_birthdays = (
        db.query(Person)
        .filter(Person.birthday.isnot(None))
        .all()
    )

    # Filter to upcoming birthdays within the next N days
    upcoming_birthdays = []
    for person in people_with_birthdays:
        # Calculate this year's birthday
        try:
            this_year_birthday = person.birthday.replace(year=today.year)
        except ValueError:
            # Handle Feb 29 for non-leap years
            this_year_birthday = person.birthday.replace(year=today.year, day=28)

        # Check if birthday has passed this year
        if this_year_birthday < today:
            # Use next year's birthday
            try:
                next_birthday = person.birthday.replace(year=today.year + 1)
            except ValueError:
                next_birthday = person.birthday.replace(year=today.year + 1, day=28)
        else:
            next_birthday = this_year_birthday

        # Calculate days until birthday
        days_until = (next_birthday - today).days

        if 0 <= days_until <= days:
            # Calculate age they'll be turning
            age = next_birthday.year - person.birthday.year

            upcoming_birthdays.append({
                "person": person,
                "birthday_date": next_birthday,
                "days_until": days_until,
                "age": age,
                "is_today": days_until == 0,
                "is_tomorrow": days_until == 1,
                "is_this_week": days_until <= 7,
            })

    # Sort by days until birthday
    upcoming_birthdays.sort(key=lambda x: x["days_until"])
    return upcoming_birthdays


def get_birthdays_for_month(db: Session, year: int, month: int) -> dict[int, list[dict]]:
    """
    Get all birthdays that fall within a specific month.

    Returns a dictionary mapping day of month to list of birthday data.
    """
    # Get all people with birthdays
    people_with_birthdays = (
        db.query(Person)
        .filter(Person.birthday.isnot(None))
        .all()
    )

    # Group birthdays by day of month
    birthdays_by_day = {}
    for person in people_with_birthdays:
        if person.birthday.month == month:
            day = person.birthday.day
            # Handle Feb 29 in non-leap years
            if month == 2 and day == 29 and not calendar.isleap(year):
                day = 28

            age = year - person.birthday.year

            if day not in birthdays_by_day:
                birthdays_by_day[day] = []

            birthdays_by_day[day].append({
                "person": person,
                "age": age,
            })

    return birthdays_by_day


@router.get("/today-widget", response_class=HTMLResponse)
async def get_today_widget(
    request: Request,
    account_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Get today's calendar widget showing meetings and today's birthdays.

    Combines calendar events for today with any birthdays occurring today.
    Also includes Google accounts for the "Add Event" feature and account filtering.

    Args:
        account_id: Optional UUID string to filter events to a specific Google account.
    """
    today = date.today()

    # Get today's birthdays
    todays_birthdays = [b for b in get_upcoming_birthdays(db, days=0) if b["is_today"]]

    # Parse account_id if provided
    selected_account_id = None
    if account_id and account_id.strip():
        try:
            selected_account_id = UUID(account_id)
        except ValueError:
            pass

    # Get today's calendar events using local timezone
    # TODO: Get timezone from user settings, for now default to America/New_York
    local_tz = ZoneInfo("America/New_York")
    events = []
    try:
        from app.services.calendar_service import get_calendar_service
        calendar_service = get_calendar_service(db)
        events = calendar_service.get_todays_events(local_tz=local_tz, account_id=selected_account_id)
        # Convert event times to local timezone for display
        for event in events:
            if event.start_time:
                event.start_time_local = event.start_time.astimezone(local_tz)
            else:
                event.start_time_local = None
            if event.end_time:
                event.end_time_local = event.end_time.astimezone(local_tz)
            else:
                event.end_time_local = None
    except Exception:
        pass

    # Get connected Google accounts for the Add Event dropdown and account filter
    accounts = db.query(GoogleAccount).filter_by(is_active=True).all()

    return templates.TemplateResponse(
        request,
        "dashboard/_today_widget.html",
        {
            "events": events,
            "birthdays": todays_birthdays,
            "today": today,
            "google_accounts": accounts,
            "selected_account_id": selected_account_id,
        },
    )


@router.get("/birthdays-widget", response_class=HTMLResponse)
async def get_birthdays_widget(
    request: Request,
    view: str = "list",
    days: int = 30,
    month: Optional[int] = None,
    year: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """
    Get upcoming birthday reminders.

    Supports two views:
    - list: Shows people with birthdays in the next N days, sorted by date
    - calendar: Shows a monthly calendar view with birthdays marked

    Handles year wrap-around (e.g., if today is Dec 20, shows Jan birthdays too).
    """
    today = date.today()

    if view == "calendar":
        # Calendar view
        display_year = year if year else today.year
        display_month = month if month else today.month

        # Get birthdays for the month
        birthdays_by_day = get_birthdays_for_month(db, display_year, display_month)

        # Generate calendar data
        cal = calendar.Calendar(firstweekday=6)  # Start on Sunday
        month_days = cal.monthdayscalendar(display_year, display_month)

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
            "dashboard/_birthdays_calendar.html",
            {
                "month_days": month_days,
                "birthdays_by_day": birthdays_by_day,
                "month_name": calendar.month_name[display_month],
                "year": display_year,
                "month": display_month,
                "today": today,
                "prev_month": prev_month,
                "prev_year": prev_year,
                "next_month": next_month,
                "next_year": next_year,
            },
        )
    else:
        # List view (default)
        upcoming_birthdays = get_upcoming_birthdays(db, days=days)

        return templates.TemplateResponse(
            request,
            "dashboard/_birthdays_widget.html",
            {
                "birthdays": upcoming_birthdays,
                "days_range": days,
            },
        )


@router.get("/tasks-widget", response_class=HTMLResponse)
async def get_tasks_widget(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Get today's tasks from Google Tasks.

    Only shows tasks that are:
    - Due today
    - Overdue (past due date)

    Tasks are separated into "Overdue" and "Due Today" sections.
    """
    # Check if we have any connected Google accounts
    accounts = db.query(GoogleAccount).filter_by(is_active=True).all()

    if not accounts:
        return templates.TemplateResponse(
            request,
            "dashboard/_tasks_widget.html",
            {
                "todays_tasks": [],
                "overdue_tasks": [],
                "due_today_tasks": [],
                "no_accounts": True,
                "error": None,
            },
        )

    # Try to fetch tasks from Google Tasks API
    try:
        from app.services.tasks_service import get_tasks_service

        tasks_service = get_tasks_service(db)
        task_lists = tasks_service.get_tasks_by_list()

        # Extract only overdue and due-today tasks from all lists
        overdue_tasks = []
        due_today_tasks = []

        for task_list in task_lists:
            for task in task_list.get("priority_tasks", []):
                # Add list info to task for display
                task["list_id"] = task_list["list_id"]
                task["list_name"] = task_list["list_name"]

                if task.get("is_overdue"):
                    overdue_tasks.append(task)
                elif task.get("is_priority") and not task.get("is_overdue"):
                    # is_priority but not overdue = due today
                    due_today_tasks.append(task)

        # Sort overdue by due date (oldest first)
        overdue_tasks.sort(key=lambda x: x.get("due_date", ""))

        # Combine for the template check
        todays_tasks = overdue_tasks + due_today_tasks

        return templates.TemplateResponse(
            request,
            "dashboard/_tasks_widget.html",
            {
                "todays_tasks": todays_tasks,
                "overdue_tasks": overdue_tasks,
                "due_today_tasks": due_today_tasks,
                "no_accounts": False,
                "error": None,
            },
        )
    except ImportError:
        # Tasks service not implemented yet
        return templates.TemplateResponse(
            request,
            "dashboard/_tasks_widget.html",
            {
                "todays_tasks": [],
                "overdue_tasks": [],
                "due_today_tasks": [],
                "no_accounts": False,
                "error": "Tasks service not available. Coming soon!",
            },
        )
    except Exception as e:
        return templates.TemplateResponse(
            request,
            "dashboard/_tasks_widget.html",
            {
                "todays_tasks": [],
                "overdue_tasks": [],
                "due_today_tasks": [],
                "no_accounts": False,
                "error": str(e),
            },
        )


@router.get("/tasks-widget-expanded", response_class=HTMLResponse)
async def get_tasks_widget_expanded(
    request: Request,
    account_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Get expanded multi-column tasks view from Google Tasks.

    Shows all tasks in a horizontal scrollable board layout,
    with each task list as a column (similar to Google Tasks UI).

    Args:
        account_id: Optional UUID string to filter tasks to a specific Google account.
    """
    # Check if we have any connected Google accounts
    accounts = db.query(GoogleAccount).filter_by(is_active=True).all()

    if not accounts:
        return templates.TemplateResponse(
            request,
            "dashboard/_tasks_widget_expanded.html",
            {
                "task_lists": [],
                "no_accounts": True,
                "error": None,
            },
        )

    # Parse account_id if provided
    selected_account_id = None
    if account_id and account_id.strip():
        try:
            selected_account_id = UUID(account_id)
        except ValueError:
            pass

    # Try to fetch tasks from Google Tasks API
    try:
        from app.services.tasks_service import get_tasks_service

        # Get saved task list order
        order_setting = db.query(Setting).filter_by(key="task_list_order").first()
        order = None
        if order_setting and order_setting.value:
            try:
                order = json.loads(order_setting.value)
            except json.JSONDecodeError:
                pass

        tasks_service = get_tasks_service(db)
        task_lists = tasks_service.get_tasks_by_list_ordered(order=order, account_id=selected_account_id)

        return templates.TemplateResponse(
            request,
            "dashboard/_tasks_widget_expanded.html",
            {
                "task_lists": task_lists,
                "no_accounts": False,
                "error": None,
            },
        )
    except ImportError:
        return templates.TemplateResponse(
            request,
            "dashboard/_tasks_widget_expanded.html",
            {
                "task_lists": [],
                "no_accounts": False,
                "error": "Tasks service not available. Coming soon!",
            },
        )
    except Exception as e:
        return templates.TemplateResponse(
            request,
            "dashboard/_tasks_widget_expanded.html",
            {
                "task_lists": [],
                "no_accounts": False,
                "error": str(e),
            },
        )


@router.post("/save-layout")
async def save_dashboard_layout(
    layout_update: DashboardLayoutUpdate,
    db: Session = Depends(get_db),
):
    """
    Save the user's preferred dashboard section order.

    Stores the order in the settings table for persistence.

    Args:
        layout_update: List of section IDs in the desired order

    Returns:
        JSON response with success status
    """
    try:
        # Store the order in settings
        setting = db.query(Setting).filter_by(key="dashboard_section_order").first()
        order_json = json.dumps(layout_update.section_order)

        if setting:
            setting.value = order_json
        else:
            setting = Setting(key="dashboard_section_order", value=order_json)
            db.add(setting)

        db.commit()

        return JSONResponse(
            content={"success": True, "order": layout_update.section_order},
            status_code=200,
        )

    except Exception as e:
        db.rollback()
        return JSONResponse(
            content={"success": False, "error": str(e)},
            status_code=500,
        )


@router.get("/mini-calendar", response_class=HTMLResponse)
async def get_mini_calendar(
    request: Request,
    month: Optional[int] = None,
    year: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """
    Get mini calendar widget for the dashboard left panel.

    Shows a compact month view with event indicators.

    Args:
        month: Month number (1-12), defaults to current month
        year: Year, defaults to current year
    """
    # Use NYC timezone since server may be in UTC
    local_tz = ZoneInfo("America/New_York")
    today = datetime.now(local_tz).date()
    display_month = month if month else today.month
    display_year = year if year else today.year

    # Generate calendar data
    cal = calendar.Calendar(firstweekday=6)  # Start on Sunday
    month_days = cal.monthdayscalendar(display_year, display_month)

    # Get birthdays for this month to mark days
    event_days = {}
    birthdays_by_day = get_birthdays_for_month(db, display_year, display_month)
    for day, birthdays in birthdays_by_day.items():
        event_days[day] = len(birthdays)

    return templates.TemplateResponse(
        request,
        "dashboard/_mini_calendar.html",
        {
            "month_days": month_days,
            "month": display_month,
            "year": display_year,
            "today": today,
            "event_days": event_days,
        },
    )


@router.get("/schedule-widget", response_class=HTMLResponse)
async def get_schedule_widget(
    request: Request,
    selected_date: Optional[str] = None,
    account_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Get schedule widget showing events for a specific day.

    Args:
        selected_date: Date in YYYY-MM-DD format. Defaults to today.
        account_id: Optional UUID string to filter events to a specific Google account.

    Returns a compact list of events with times for the selected day.
    """
    local_tz = ZoneInfo("America/New_York")
    events = []
    display_date = None
    is_today = True

    # Parse account_id if provided
    selected_account_id = None
    if account_id and account_id.strip():
        try:
            selected_account_id = UUID(account_id)
        except ValueError:
            pass

    # Parse selected date or use today (use NYC timezone since server may be UTC)
    today_in_tz = datetime.now(local_tz).date()
    if selected_date:
        try:
            display_date = datetime.strptime(selected_date, "%Y-%m-%d").date()
            is_today = display_date == today_in_tz
        except ValueError:
            display_date = today_in_tz
    else:
        display_date = today_in_tz

    try:
        from app.services.calendar_service import get_calendar_service
        calendar_service = get_calendar_service(db)

        if is_today:
            events = calendar_service.get_todays_events(local_tz=local_tz, account_id=selected_account_id)
        else:
            # Get events for the selected date using upcoming_events with date range
            all_events = calendar_service.get_upcoming_events(days=60, account_id=selected_account_id)
            events = [
                e for e in all_events
                if e.start_time and e.start_time.astimezone(local_tz).date() == display_date
            ]

        # Convert event times to local timezone
        for event in events:
            if event.start_time:
                event.start_time_local = event.start_time.astimezone(local_tz)
            else:
                event.start_time_local = None
    except Exception:
        pass

    return templates.TemplateResponse(
        request,
        "dashboard/_schedule_widget.html",
        {
            "events": events,
            "selected_date": display_date,
            "is_today": is_today,
        },
    )


@router.get("/birthdays-compact", response_class=HTMLResponse)
async def get_birthdays_compact(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Get compact birthdays widget for dashboard left panel.

    Shows today's birthdays with Send buttons and upcoming birthdays.
    """
    upcoming_birthdays = get_upcoming_birthdays(db, days=30)

    return templates.TemplateResponse(
        request,
        "dashboard/_birthdays_compact.html",
        {"birthdays": upcoming_birthdays},
    )


@router.get("/tasks-panel", response_class=HTMLResponse)
async def get_tasks_panel(
    request: Request,
    view: str = "today",
    account_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Get tasks panel for the dashboard right panel.

    Shows tasks filtered by view:
    - today: overdue + due today
    - tomorrow: due tomorrow
    - week: due within next 7 days

    Args:
        view: Filter view - today, tomorrow, or week
        account_id: Optional UUID string to filter tasks to a specific Google account.
    """
    accounts = db.query(GoogleAccount).filter_by(is_active=True).all()

    if not accounts:
        return templates.TemplateResponse(
            request,
            "dashboard/_tasks_panel.html",
            {
                "tasks": [],
                "overdue_tasks": [],
                "days": [],
                "total_tasks": 0,
                "no_accounts": True,
                "error": None,
                "view": view,
            },
        )

    # Parse account_id if provided
    selected_account_id = None
    if account_id and account_id.strip():
        try:
            selected_account_id = UUID(account_id)
        except ValueError:
            pass

    try:
        from app.services.tasks_service import get_tasks_service

        tasks_service = get_tasks_service(db)
        task_lists = tasks_service.get_tasks_by_list(account_id=selected_account_id)

        # Use NYC timezone for "today" calculation (server may be in UTC)
        local_tz = ZoneInfo("America/New_York")
        today = datetime.now(local_tz).date()
        week_end = today + timedelta(days=6)  # Show 7 days including today

        overdue_tasks = []
        # Create a dict to hold tasks grouped by date
        tasks_by_date = {}

        # Initialize the 7 days
        for i in range(7):
            day_date = today + timedelta(days=i)
            tasks_by_date[day_date] = []

        for task_list in task_lists:
            # Process priority tasks
            for task in task_list.get("priority_tasks", []):
                task["list_id"] = task_list["list_id"]
                task["list_name"] = task_list["list_name"]

                # Parse due date
                due_date = None
                if task.get("due_date"):
                    try:
                        due_date = datetime.strptime(task["due_date"], "%Y-%m-%d").date()
                    except ValueError:
                        pass

                if task.get("is_overdue"):
                    overdue_tasks.append(task)
                elif due_date and today <= due_date <= week_end:
                    if due_date in tasks_by_date:
                        tasks_by_date[due_date].append(task)

            # Also include other tasks with due dates in range
            for task in task_list.get("other_tasks", []):
                if task.get("due_date"):
                    try:
                        due_date = datetime.strptime(task["due_date"], "%Y-%m-%d").date()
                        if today <= due_date <= week_end:
                            task["list_id"] = task_list["list_id"]
                            task["list_name"] = task_list["list_name"]
                            if due_date in tasks_by_date:
                                tasks_by_date[due_date].append(task)
                    except ValueError:
                        pass

        # Sort overdue tasks
        overdue_tasks.sort(key=lambda x: x.get("due_date", ""))

        # Build days list for template
        days = []
        total_tasks = len(overdue_tasks)
        for i in range(7):
            day_date = today + timedelta(days=i)
            day_tasks = tasks_by_date.get(day_date, [])
            total_tasks += len(day_tasks)
            days.append({
                "date": day_date,
                "date_str": day_date.strftime("%Y-%m-%d"),
                "display_date": day_date.strftime("%b %d, %Y"),  # e.g., "Dec 22, 2025"
                "day_name": day_date.strftime("%A").upper(),  # e.g., "MONDAY"
                "day_short": day_date.strftime("%a").upper(),  # e.g., "MON"
                "is_today": day_date == today,
                "tasks": day_tasks,
                "task_count": len(day_tasks),
            })

        return templates.TemplateResponse(
            request,
            "dashboard/_tasks_panel.html",
            {
                "tasks": [],  # Not used in new layout
                "overdue_tasks": overdue_tasks,
                "days": days,
                "total_tasks": total_tasks,
                "no_accounts": False,
                "error": None,
                "view": view,
            },
        )

    except ImportError:
        return templates.TemplateResponse(
            request,
            "dashboard/_tasks_panel.html",
            {
                "tasks": [],
                "overdue_tasks": [],
                "days": [],
                "total_tasks": 0,
                "no_accounts": False,
                "error": "Tasks service not available.",
                "view": view,
            },
        )
    except Exception as e:
        return templates.TemplateResponse(
            request,
            "dashboard/_tasks_panel.html",
            {
                "tasks": [],
                "overdue_tasks": [],
                "days": [],
                "total_tasks": 0,
                "no_accounts": False,
                "error": str(e),
                "view": view,
            },
        )


@router.get("/add-task-modal", response_class=HTMLResponse)
async def get_add_task_modal(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Get the add task modal with available task lists.

    Returns the modal HTML with a dropdown populated with task lists
    from Google Tasks.
    """
    task_lists = []

    try:
        from app.services.tasks_service import get_tasks_service

        tasks_service = get_tasks_service(db)
        all_lists = tasks_service.get_tasks_by_list()

        # Extract just list info for the dropdown
        task_lists = [
            {"list_id": tl["list_id"], "list_name": tl["list_name"]}
            for tl in all_lists
        ]
    except Exception:
        pass

    return templates.TemplateResponse(
        request,
        "dashboard/_add_task_modal.html",
        {"task_lists": task_lists},
    )


@router.get("/add-event-form", response_class=HTMLResponse)
async def get_add_event_form(
    request: Request,
    event_id: Optional[str] = None,
    account_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Get the add/edit event modal with available Google accounts.

    Returns the modal HTML with a dropdown populated with connected
    Google accounts for calendar selection.

    Args:
        event_id: Optional Google Calendar event ID. If provided, loads
                  the event data for editing.
        account_id: Optional Google account UUID. Required if event_id is provided.
    """
    # Get connected Google accounts for the calendar dropdown
    accounts = db.query(GoogleAccount).filter_by(is_active=True).all()

    # Check if we're editing an existing event
    event_data = None
    edit_mode = False
    selected_account_id = None

    if event_id and account_id:
        edit_mode = True
        try:
            selected_account_id = UUID(account_id)
            from app.services.calendar_service import get_calendar_service
            calendar_service = get_calendar_service(db)

            # Get the event from Google Calendar
            event = calendar_service.get_event(event_id, selected_account_id)

            if event:
                # Parse event data for the form
                local_tz = ZoneInfo("America/New_York")

                # Parse start time
                start = event.get("start", {})
                start_datetime = None
                event_timezone = start.get("timeZone", "America/New_York")

                if "dateTime" in start:
                    start_datetime = datetime.fromisoformat(
                        start["dateTime"].replace("Z", "+00:00")
                    ).astimezone(local_tz)
                elif "date" in start:
                    start_datetime = datetime.strptime(start["date"], "%Y-%m-%d")

                # Parse end time
                end = event.get("end", {})
                end_datetime = None
                if "dateTime" in end:
                    end_datetime = datetime.fromisoformat(
                        end["dateTime"].replace("Z", "+00:00")
                    ).astimezone(local_tz)

                # Parse attendees
                attendees = []
                for attendee in event.get("attendees", []):
                    if not attendee.get("self"):
                        attendees.append({
                            "email": attendee.get("email", ""),
                            "name": attendee.get("displayName", ""),
                        })

                # Check for video conferencing
                has_video = bool(event.get("conferenceData"))

                # Parse recurrence
                recurrence = None
                if event.get("recurrence"):
                    recurrence = event["recurrence"][0] if event["recurrence"] else None

                event_data = {
                    "google_event_id": event_id,
                    "summary": event.get("summary", ""),
                    "description": event.get("description", ""),
                    "location": event.get("location", ""),
                    "date": start_datetime.strftime("%Y-%m-%d") if start_datetime else "",
                    "start_time": start_datetime.strftime("%H:%M") if start_datetime else "",
                    "end_time": end_datetime.strftime("%H:%M") if end_datetime else "",
                    "timezone": event_timezone,
                    "attendees": attendees,
                    "has_video": has_video,
                    "recurrence": recurrence,
                }
        except Exception as e:
            # If we can't load the event, fall back to new event mode
            print(f"Error loading event for edit: {e}")
            edit_mode = False

    return templates.TemplateResponse(
        request,
        "dashboard/_add_event_modal.html",
        {
            "google_accounts": accounts,
            "edit_mode": edit_mode,
            "event": event_data,
            "selected_account_id": str(selected_account_id) if selected_account_id else None,
        },
    )


@router.get("/api/google-accounts")
async def get_google_accounts(db: Session = Depends(get_db)):
    """
    Get list of active Google accounts for the dashboard filter.

    Returns JSON with accounts array containing id and email for each account.
    """
    accounts = db.query(GoogleAccount).filter_by(is_active=True).all()
    return JSONResponse(content={
        "accounts": [
            {"id": str(a.id), "email": a.email}
            for a in accounts
        ]
    })


@router.get("/quick-add-person", response_class=HTMLResponse)
async def get_quick_add_person_form(
    request: Request,
    email: Optional[str] = None,
    name: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Get a quick add person form pre-populated with email and name.

    This is a simplified version of the full add person form,
    designed for quick additions from calendar event attendees.

    Args:
        email: Email address to pre-populate
        name: Display name to pre-populate (will be split into first/last)
    """
    # Parse name into first and last name
    first_name = ""
    last_name = ""
    if name:
        name_parts = name.strip().split(" ", 1)
        first_name = name_parts[0] if len(name_parts) > 0 else ""
        last_name = name_parts[1] if len(name_parts) > 1 else ""

    return templates.TemplateResponse(
        request,
        "dashboard/_quick_add_person.html",
        {
            "email": email or "",
            "first_name": first_name,
            "last_name": last_name,
        },
    )


@router.post("/quick-add-person")
async def create_quick_person(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Quick create a person with name and email.

    Used when adding contacts from calendar event attendees.
    Creates the person and adds their email.

    Returns:
        JSON with success status and the new person's info
    """
    form = await request.form()
    first_name = form.get("first_name", "").strip()
    last_name = form.get("last_name", "").strip()
    email = form.get("email", "").strip()

    if not first_name:
        return JSONResponse(
            content={"success": False, "error": "First name is required"},
            status_code=400,
        )

    # Build full_name
    full_name = first_name
    if last_name:
        full_name = f"{first_name} {last_name}"

    # Check if person with this email already exists
    if email:
        existing_email = db.query(PersonEmail).filter(
            PersonEmail.email.ilike(email)
        ).first()
        if existing_email:
            person = existing_email.person
            return JSONResponse(content={
                "success": True,
                "person_id": str(person.id),
                "name": person.full_name,
                "existing": True,
                "message": f"Found existing contact: {person.full_name}",
            })

    # Create new person
    new_person = Person(
        first_name=first_name,
        last_name=last_name if last_name else None,
        full_name=full_name,
    )
    db.add(new_person)
    db.flush()  # Get the ID

    # Add email if provided
    if email:
        new_email = PersonEmail(
            person_id=new_person.id,
            email=email,
            is_primary=True,
        )
        db.add(new_email)

    db.commit()
    db.refresh(new_person)

    return JSONResponse(content={
        "success": True,
        "person_id": str(new_person.id),
        "name": new_person.full_name,
        "existing": False,
        "message": f"Added {new_person.full_name} to BlackBook",
    })


@router.get("/people-search")
async def search_people_for_guests(
    q: str = "",
    db: Session = Depends(get_db),
):
    """
    Search for people to add as calendar event guests.

    Returns JSON array of people with their emails for typeahead suggestions.

    Args:
        q: Search query (matches first name, last name, or email)

    Returns:
        List of people with id, name, and list of emails
    """
    if len(q) < 2:
        return JSONResponse(content={"results": []})

    search_term = f"%{q}%"

    # Search people by name
    people = (
        db.query(Person)
        .filter(
            or_(
                Person.first_name.ilike(search_term),
                Person.last_name.ilike(search_term),
                Person.full_name.ilike(search_term),
            )
        )
        .limit(10)
        .all()
    )

    # Also search by email in PersonEmail table
    email_matches = (
        db.query(PersonEmail)
        .filter(PersonEmail.email.ilike(search_term))
        .limit(10)
        .all()
    )

    # Add people from email matches that aren't already in results
    person_ids = {p.id for p in people}
    for pe in email_matches:
        if pe.person_id not in person_ids:
            if pe.person:
                people.append(pe.person)
                person_ids.add(pe.person_id)

    # Build results with person name and all their emails
    results = []
    for person in people[:15]:  # Limit to 15 total
        # Get all emails for this person
        emails = [
            {
                "email": pe.email,
                "label": pe.label.value if pe.label else "other",
                "is_primary": pe.is_primary,
            }
            for pe in person.emails
        ] if hasattr(person, 'emails') and person.emails else []

        # If no emails in PersonEmail table, check legacy email field
        if not emails and person.email:
            emails = [{"email": person.email, "label": "primary", "is_primary": True}]

        # Only include people who have at least one email
        if emails:
            results.append({
                "id": str(person.id),
                "name": person.full_name or f"{person.first_name} {person.last_name or ''}".strip(),
                "emails": emails,
            })

    return JSONResponse(content={"results": results})


@router.get("/event-detail/{google_event_id}", response_class=HTMLResponse)
async def get_event_detail(
    request: Request,
    google_event_id: str,
    account_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Get event detail modal for viewing.

    Args:
        google_event_id: Google Calendar event ID
        account_id: Optional Google account UUID to narrow down the search

    Returns:
        HTML modal with event details and matched attendees
    """
    local_tz = ZoneInfo("America/New_York")

    # Find the event in the database (eager load google_account for calendar URL)
    query = (
        db.query(CalendarEvent)
        .options(joinedload(CalendarEvent.google_account))
        .filter(CalendarEvent.google_event_id == google_event_id)
    )

    if account_id:
        try:
            account_uuid = UUID(account_id)
            query = query.filter(CalendarEvent.google_account_id == account_uuid)
        except ValueError:
            pass

    event = query.first()

    if not event:
        return HTMLResponse(
            content='<div class="text-red-400 p-4">Event not found</div>',
            status_code=404
        )

    # Add local time properties
    if event.start_time:
        event.start_time_local = event.start_time.astimezone(local_tz)
    else:
        event.start_time_local = None
    if event.end_time:
        event.end_time_local = event.end_time.astimezone(local_tz)
    else:
        event.end_time_local = None

    # Match attendees to persons in BlackBook
    try:
        from app.services.calendar_service import get_calendar_service
        calendar_service = get_calendar_service(db)
        matched_attendees = calendar_service.match_attendees_to_persons(event)
    except Exception:
        matched_attendees = []

    # Count known attendees
    known_attendee_count = len([a for a in matched_attendees if a.get("person_id")])

    return templates.TemplateResponse(
        request,
        "dashboard/_event_detail_modal.html",
        {
            "event": event,
            "attendees": matched_attendees,
            "known_attendee_count": known_attendee_count,
        },
    )


@router.delete("/event/{google_event_id}")
async def delete_event(
    google_event_id: str,
    account_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Delete an event from Google Calendar.

    Args:
        google_event_id: Google Calendar event ID
        account_id: Google account UUID (required to know which account to delete from)

    Returns:
        JSON response with success status
    """
    if not account_id:
        return JSONResponse(
            content={"success": False, "error": "Account ID required"},
            status_code=400
        )

    try:
        account_uuid = UUID(account_id)
    except ValueError:
        return JSONResponse(
            content={"success": False, "error": "Invalid account ID"},
            status_code=400
        )

    # Get the account
    account = db.query(GoogleAccount).filter_by(id=account_uuid, is_active=True).first()
    if not account:
        return JSONResponse(
            content={"success": False, "error": "Account not found"},
            status_code=404
        )

    try:
        from app.services.calendar_service import get_calendar_service
        calendar_service = get_calendar_service(db)
        success = calendar_service.delete_event(google_event_id, account_uuid)

        if success:
            # Also delete from local cache
            local_event = db.query(CalendarEvent).filter_by(
                google_event_id=google_event_id,
                google_account_id=account_uuid
            ).first()
            if local_event:
                db.delete(local_event)
                db.commit()

            return JSONResponse(content={"success": True})
        else:
            return JSONResponse(
                content={"success": False, "error": "Failed to delete from Google Calendar"},
                status_code=500
            )
    except Exception as e:
        return JSONResponse(
            content={"success": False, "error": str(e)},
            status_code=500
        )


# =============================================================================
# Calendar Full View Endpoints (Day/Week/Month/Schedule)
# =============================================================================

@router.get("/calendar-view/day", response_class=HTMLResponse)
async def get_calendar_day_view(
    request: Request,
    date: Optional[str] = None,
    account_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Render day view with hourly grid.

    Args:
        date: Date in YYYY-MM-DD format. Defaults to today.
        account_id: Optional UUID string to filter events to a specific Google account.
    """
    local_tz = ZoneInfo("America/New_York")
    now_local = datetime.now(local_tz)

    # Parse date
    if date:
        try:
            view_date = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            view_date = now_local.date()
    else:
        view_date = now_local.date()

    is_today = view_date == now_local.date()

    # Parse account_id if provided
    selected_account_id = None
    if account_id and account_id.strip():
        try:
            selected_account_id = UUID(account_id)
        except ValueError:
            pass

    # Get events for this day
    events = []
    try:
        from app.services.calendar_service import get_calendar_service
        calendar_service = get_calendar_service(db)

        # Get events for this specific day using precise date range
        # Use localize pattern for proper timezone assignment
        from datetime import time as dt_time
        day_start_naive = datetime.combine(view_date, dt_time.min)
        day_start = day_start_naive.replace(tzinfo=local_tz)
        day_end = day_start + timedelta(days=1)

        all_events = calendar_service.get_events_for_range(
            start_date=day_start,
            end_date=day_end,
            account_id=selected_account_id,
        )

        # Process events - add local time conversions
        for event in all_events:
            if event.start_time:
                event.start_time_local = event.start_time.astimezone(local_tz)
                event.end_time_local = event.end_time.astimezone(local_tz) if event.end_time else None
                # is_all_day is already a property on CalendarEvent model
                events.append(event)
    except Exception:
        pass

    # Get pending tasks count for this day
    pending_tasks_count = 0
    try:
        from app.services.tasks_service import get_tasks_service
        tasks_service = get_tasks_service(db)
        task_lists = tasks_service.get_tasks_by_list(account_id=selected_account_id)

        for task_list in task_lists:
            for task in task_list.get("priority_tasks", []):
                if task.get("due_date"):
                    try:
                        due_date = datetime.strptime(task["due_date"], "%Y-%m-%d").date()
                        if due_date == view_date or task.get("is_overdue"):
                            pending_tasks_count += 1
                    except ValueError:
                        pass
    except Exception:
        pass

    return templates.TemplateResponse(
        request,
        "dashboard/calendar/_day_view.html",
        {
            "view_date": view_date,
            "is_today": is_today,
            "hours": list(range(24)),
            "events": events,
            "pending_tasks_count": pending_tasks_count if is_today else 0,
            "current_hour": now_local.hour,
            "current_minute": now_local.minute,
        },
    )


@router.get("/calendar-view/week", response_class=HTMLResponse)
async def get_calendar_week_view(
    request: Request,
    date: Optional[str] = None,
    account_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Render week view with 7-day hourly grid.

    Args:
        date: Date in YYYY-MM-DD format. Defaults to today.
        account_id: Optional UUID string to filter events to a specific Google account.
    """
    local_tz = ZoneInfo("America/New_York")
    now_local = datetime.now(local_tz)

    # Parse date
    if date:
        try:
            view_date = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            view_date = now_local.date()
    else:
        view_date = now_local.date()

    # Get Monday of this week
    monday = view_date - timedelta(days=view_date.weekday())

    # Parse account_id if provided
    selected_account_id = None
    if account_id and account_id.strip():
        try:
            selected_account_id = UUID(account_id)
        except ValueError:
            pass

    # Build 7 days
    days = []
    today = now_local.date()
    for i in range(7):
        day_date = monday + timedelta(days=i)
        days.append({
            "date": day_date,
            "day_name": day_date.strftime("%a").upper(),
            "day_num": day_date.day,
            "is_today": day_date == today,
        })

    # Get events for the week
    all_day_events = []
    timed_events = []
    try:
        from app.services.calendar_service import get_calendar_service
        calendar_service = get_calendar_service(db)

        # Get events for the week using precise date range
        week_start = datetime.combine(monday, datetime.min.time()).replace(tzinfo=local_tz)
        week_end = week_start + timedelta(days=7)

        week_events = calendar_service.get_events_for_range(
            start_date=week_start,
            end_date=week_end,
            account_id=selected_account_id,
        )

        sunday = monday + timedelta(days=6)
        for event in week_events:
            if event.start_time:
                event.start_time_local = event.start_time.astimezone(local_tz)
                event.end_time_local = event.end_time.astimezone(local_tz) if event.end_time else None

                # Use model's is_all_day property
                if event.is_all_day:
                    all_day_events.append(event)
                else:
                    timed_events.append(event)
    except Exception:
        pass

    # Get pending tasks count for today
    pending_tasks_count = 0
    try:
        from app.services.tasks_service import get_tasks_service
        tasks_service = get_tasks_service(db)
        task_lists = tasks_service.get_tasks_by_list(account_id=selected_account_id)

        for task_list in task_lists:
            for task in task_list.get("priority_tasks", []):
                if task.get("is_overdue") or task.get("is_priority"):
                    pending_tasks_count += 1
    except Exception:
        pass

    # Check if current week includes today
    show_current_time = monday <= today <= sunday

    return templates.TemplateResponse(
        request,
        "dashboard/calendar/_week_view.html",
        {
            "days": days,
            "hours": list(range(24)),
            "all_day_events": all_day_events,
            "timed_events": timed_events,
            "pending_tasks_count": pending_tasks_count,
            "current_hour": now_local.hour,
            "current_minute": now_local.minute,
            "show_current_time": show_current_time,
        },
    )


@router.get("/calendar-view/month", response_class=HTMLResponse)
async def get_calendar_month_view(
    request: Request,
    date: Optional[str] = None,
    account_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Render month view grid.

    Args:
        date: Date in YYYY-MM-DD format. Defaults to today.
        account_id: Optional UUID string to filter events to a specific Google account.
    """
    local_tz = ZoneInfo("America/New_York")
    now_local = datetime.now(local_tz)
    today = now_local.date()

    # Parse date
    if date:
        try:
            view_date = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            view_date = today
    else:
        view_date = today

    # Parse account_id if provided
    selected_account_id = None
    if account_id and account_id.strip():
        try:
            selected_account_id = UUID(account_id)
        except ValueError:
            pass

    # Get first day of month
    first_of_month = view_date.replace(day=1)

    # Get start of calendar grid (Monday of first week)
    start_day = first_of_month - timedelta(days=first_of_month.weekday())

    # Build 6 weeks (42 days) for the grid
    weeks = []
    current_day = start_day
    for week_num in range(6):
        week = []
        for day_num in range(7):
            week.append({
                "date": current_day,
                "day_num": current_day.day,
                "is_today": current_day == today,
                "is_current_month": current_day.month == view_date.month,
                "events": [],
            })
            current_day += timedelta(days=1)
        weeks.append(week)

    # Get events for the visible range (42 days)
    end_day = start_day + timedelta(days=42)
    try:
        from app.services.calendar_service import get_calendar_service
        calendar_service = get_calendar_service(db)

        # Get events for the month grid using precise date range
        grid_start = datetime.combine(start_day, datetime.min.time()).replace(tzinfo=local_tz)
        grid_end = datetime.combine(end_day, datetime.min.time()).replace(tzinfo=local_tz)

        month_events = calendar_service.get_events_for_range(
            start_date=grid_start,
            end_date=grid_end,
            account_id=selected_account_id,
        )

        # Assign events to days
        for event in month_events:
            if event.start_time:
                event_date = event.start_time.astimezone(local_tz).date()
                if start_day <= event_date < end_day:
                    event.start_time_local = event.start_time.astimezone(local_tz)
                    event.end_time_local = event.end_time.astimezone(local_tz) if event.end_time else None
                    # is_all_day is already a property on CalendarEvent model

                    # Find the day and add event
                    for week in weeks:
                        for day in week:
                            if day["date"] == event_date:
                                day["events"].append(event)
                                break
    except Exception:
        pass

    return templates.TemplateResponse(
        request,
        "dashboard/calendar/_month_view.html",
        {
            "weeks": weeks,
            "month_name": view_date.strftime("%B"),
            "year": view_date.year,
            "today": today,
            "day_headers": ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"],
        },
    )


@router.get("/calendar-view/schedule", response_class=HTMLResponse)
async def get_calendar_schedule_view(
    request: Request,
    date: Optional[str] = None,
    account_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Render agenda/schedule view.

    Args:
        date: Date in YYYY-MM-DD format. Defaults to today.
        account_id: Optional UUID string to filter events to a specific Google account.
    """
    local_tz = ZoneInfo("America/New_York")
    now_local = datetime.now(local_tz)
    today = now_local.date()

    # Parse date
    if date:
        try:
            view_date = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            view_date = today
    else:
        view_date = today

    # Parse account_id if provided
    selected_account_id = None
    if account_id and account_id.strip():
        try:
            selected_account_id = UUID(account_id)
        except ValueError:
            pass

    # Get events for next 14 days
    try:
        from app.services.calendar_service import get_calendar_service
        calendar_service = get_calendar_service(db)

        # Get events for 14 days from the view date
        schedule_start = datetime.combine(view_date, datetime.min.time()).replace(tzinfo=local_tz)
        schedule_end = schedule_start + timedelta(days=14)

        events = calendar_service.get_events_for_range(
            start_date=schedule_start,
            end_date=schedule_end,
            account_id=selected_account_id,
        )

        # Get pending tasks per day
        pending_by_date = {}
        try:
            from app.services.tasks_service import get_tasks_service
            tasks_service = get_tasks_service(db)
            task_lists = tasks_service.get_tasks_by_list(account_id=selected_account_id)

            for task_list in task_lists:
                for task in task_list.get("priority_tasks", []):
                    if task.get("due_date"):
                        try:
                            due_date = datetime.strptime(task["due_date"], "%Y-%m-%d").date()
                            if due_date not in pending_by_date:
                                pending_by_date[due_date] = 0
                            pending_by_date[due_date] += 1
                        except ValueError:
                            pass
        except Exception:
            pass

        # Group events by day
        days_dict = {}
        for event in events:
            if event.start_time:
                event_date = event.start_time.astimezone(local_tz).date()
                if event_date >= view_date:
                    if event_date not in days_dict:
                        days_dict[event_date] = {
                            "date": event_date,
                            "day_name": event_date.strftime("%a").upper(),
                            "month": event_date.strftime("%b").upper(),
                            "day_num": event_date.day,
                            "is_today": event_date == today,
                            "events": [],
                            "pending_tasks_count": pending_by_date.get(event_date, 0),
                        }

                    event.start_time_local = event.start_time.astimezone(local_tz)
                    event.end_time_local = event.end_time.astimezone(local_tz) if event.end_time else None
                    # is_all_day is already a property on CalendarEvent model

                    days_dict[event_date]["events"].append(event)

        # Sort by date
        sorted_days = sorted(days_dict.values(), key=lambda d: d["date"])

    except Exception:
        sorted_days = []

    return templates.TemplateResponse(
        request,
        "dashboard/calendar/_schedule_view.html",
        {
            "days": sorted_days,
        },
    )
