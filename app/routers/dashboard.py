"""
Dashboard router for widget endpoints.

Provides HTMX endpoints for dashboard widgets including:
- Today's calendar (meetings + today's birthdays)
- Birthday reminders (list and calendar views)
- Tasks widget (Google Tasks integration)
- Dashboard layout management
"""

import calendar
import json
from datetime import date, timedelta
from typing import Optional
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import extract, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Person, GoogleAccount, Setting, PersonEmail


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
    db: Session = Depends(get_db),
):
    """
    Get expanded multi-column tasks view from Google Tasks.

    Shows all tasks in a horizontal scrollable board layout,
    with each task list as a column (similar to Google Tasks UI).
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
        task_lists = tasks_service.get_tasks_by_list_ordered(order=order)

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
