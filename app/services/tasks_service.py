"""
Google Tasks Service.

Provides integration with Google Tasks API for task management.
"""

import logging
from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials
from sqlalchemy.orm import Session

from app.models import GoogleAccount
from app.services.google_auth import TASKS_SCOPES

logger = logging.getLogger(__name__)


class TasksServiceError(Exception):
    """Base exception for Tasks service errors."""
    pass


class TasksAuthError(TasksServiceError):
    """Authentication/authorization error."""
    pass


class TasksAPIError(TasksServiceError):
    """Google Tasks API error."""
    pass


class TasksService:
    """
    Service for managing Google Tasks.

    Handles:
    - Fetching task lists
    - Getting tasks for today
    - Syncing tasks
    """

    def __init__(self, db: Session):
        self.db = db

    def _get_credentials(self, account: GoogleAccount) -> Credentials:
        """Get Google credentials for an account."""
        creds_dict = account.get_credentials()

        credentials = Credentials(
            token=creds_dict.get("token"),
            refresh_token=creds_dict.get("refresh_token"),
            token_uri=creds_dict.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=creds_dict.get("client_id"),
            client_secret=creds_dict.get("client_secret"),
            scopes=creds_dict.get("scopes", TASKS_SCOPES),
        )

        return credentials

    def get_all_task_lists(self) -> list[dict[str, Any]]:
        """
        Get all task lists from connected accounts (including empty lists).

        Returns:
            List of task list dictionaries, each containing:
            - list_id: Task list ID
            - list_name: Task list name
        """
        all_lists = []
        accounts = self.db.query(GoogleAccount).filter_by(is_active=True).all()
        print(f"[DEBUG] get_all_task_lists: found {len(accounts)} active accounts")

        for account in accounts:
            try:
                print(f"[DEBUG] Processing account {account.id} ({account.email})")
                credentials = self._get_credentials(account)
                service = build("tasks", "v1", credentials=credentials)

                task_lists_result = service.tasklists().list().execute()
                task_lists = task_lists_result.get("items", [])
                print(f"[DEBUG] Account {account.email} has {len(task_lists)} task lists")

                for task_list in task_lists:
                    all_lists.append({
                        "list_id": task_list.get("id"),
                        "list_name": task_list.get("title", "Untitled"),
                    })

            except Exception as e:
                logger.error(f"Error getting task lists for account {account.id}: {e}")
                continue

        logger.info(f"get_all_task_lists found {len(all_lists)} lists from {len(accounts)} accounts")
        # Sort by name
        all_lists.sort(key=lambda x: x["list_name"].lower())
        return all_lists

    def get_tasks_by_list(self, account_id: UUID | None = None) -> list[dict[str, Any]]:
        """
        Get all tasks grouped by task list from connected accounts.

        Args:
            account_id: Optional UUID to filter tasks to a specific Google account.
                       If None, returns tasks from all active accounts.

        Returns:
            List of task list dictionaries, each containing:
            - list_id: Task list ID
            - list_name: Task list name
            - tasks: List of tasks in this list, each with:
                - id: Task ID
                - title: Task title
                - notes: Task notes/description
                - due_date: Due date string
                - completed: Whether task is completed
                - is_priority: Whether task is high priority (due today or overdue)
                - is_overdue: Whether task is overdue
        """
        all_task_lists = []
        today = date.today()

        # Get accounts based on filter
        if account_id:
            account = self.db.query(GoogleAccount).filter_by(id=account_id, is_active=True).first()
            accounts = [account] if account else []
        else:
            accounts = self.db.query(GoogleAccount).filter_by(is_active=True).all()
        print(f"Tasks: Found {len(accounts)} active Google accounts (filter: {account_id})")

        for account in accounts:
            try:
                print(f"Tasks: Fetching tasks for account {account.email}")
                credentials = self._get_credentials(account)
                service = build("tasks", "v1", credentials=credentials)

                # Get all task lists
                task_lists_result = service.tasklists().list().execute()
                print(f"Tasks: Found {len(task_lists_result.get('items', []))} task lists for {account.email}")
                task_lists = task_lists_result.get("items", [])

                for task_list in task_lists:
                    list_data = {
                        "list_id": task_list.get("id"),
                        "list_name": task_list.get("title", "Untitled"),
                        "tasks": [],
                        "priority_tasks": [],  # Tasks with due dates (overdue or due soon)
                        "other_tasks": [],  # Tasks with no due date
                    }

                    # Get tasks from each list
                    tasks_result = service.tasks().list(
                        tasklist=task_list["id"],
                        showCompleted=False,
                        showHidden=False,
                    ).execute()

                    tasks = tasks_result.get("items", [])

                    for task in tasks:
                        # Skip tasks without a title (usually empty tasks)
                        if not task.get("title", "").strip():
                            continue

                        task_data = {
                            "id": task.get("id"),
                            "title": task.get("title", "Untitled"),
                            "notes": task.get("notes", ""),
                            "completed": task.get("status") == "completed",
                            "is_priority": False,
                            "is_overdue": False,
                            "due_date": None,
                            "due_date_display": None,
                            "due_time": None,
                            "due_time_display": None,
                            "parent_id": task.get("parent"),  # Parent task ID for subtasks
                            "is_subtask": bool(task.get("parent")),
                            "subtasks": [],  # Will be populated after processing all tasks
                        }

                        # Parse due date if present
                        due = task.get("due")
                        if due:
                            try:
                                # Google Tasks uses RFC 3339 format
                                due_dt = datetime.fromisoformat(due.replace("Z", "+00:00"))
                                local_tz = ZoneInfo("America/New_York")

                                # Check if this is a date-only task (midnight UTC)
                                # Google stores date-only tasks as T00:00:00.000Z
                                is_date_only = (due_dt.hour == 0 and due_dt.minute == 0 and due_dt.second == 0)

                                if is_date_only:
                                    # For date-only tasks, extract the date directly from UTC
                                    # to avoid timezone shift issues
                                    due_date = due_dt.date()
                                    task_data["due_date"] = due_date.strftime("%Y-%m-%d")
                                    task_data["due_date_display"] = due_date.strftime("%b %d, %Y")
                                    # No time for date-only tasks
                                else:
                                    # Task has a specific time - convert to local timezone
                                    due_local = due_dt.astimezone(local_tz)
                                    due_date = due_local.date()
                                    task_data["due_date"] = due_date.strftime("%Y-%m-%d")
                                    task_data["due_date_display"] = due_date.strftime("%b %d, %Y")
                                    task_data["due_time"] = due_local.strftime("%H:%M")
                                    task_data["due_time_display"] = due_local.strftime("%I:%M %p").lstrip("0")

                                # Check if overdue or due today
                                if due_date < today:
                                    task_data["is_overdue"] = True
                                    task_data["is_priority"] = True
                                elif due_date == today:
                                    task_data["is_priority"] = True
                                    task_data["due_date_display"] = "Today"
                                elif due_date == today.replace(day=today.day + 1) if today.day < 28 else today:
                                    task_data["due_date_display"] = "Tomorrow"
                            except (ValueError, AttributeError):
                                pass

                        list_data["tasks"].append(task_data)

                    # Build hierarchical structure: nest subtasks under parents
                    tasks_by_id = {t["id"]: t for t in list_data["tasks"]}
                    top_level_tasks = []

                    for task_data in list_data["tasks"]:
                        if task_data["is_subtask"] and task_data["parent_id"] in tasks_by_id:
                            # Add as subtask of parent
                            parent = tasks_by_id[task_data["parent_id"]]
                            parent["subtasks"].append(task_data)
                        else:
                            # Top-level task (or orphaned subtask)
                            top_level_tasks.append(task_data)

                    # Sort subtasks within each parent by position (Google's default order)
                    for task_data in top_level_tasks:
                        if task_data["subtasks"]:
                            # Keep original order from API
                            pass

                    # Separate into priority and other (only top-level tasks)
                    for task_data in top_level_tasks:
                        if task_data["due_date"]:
                            list_data["priority_tasks"].append(task_data)
                        else:
                            list_data["other_tasks"].append(task_data)

                    # Sort priority tasks by due date (overdue first)
                    list_data["priority_tasks"].sort(
                        key=lambda x: (not x["is_overdue"], x["due_date"] or "9999-99-99")
                    )

                    # Only add lists that have tasks
                    if list_data["tasks"]:
                        all_task_lists.append(list_data)

            except HttpError as e:
                print(f"Tasks: HttpError for {account.email}: {e}")
                continue
            except Exception as e:
                print(f"Tasks: Exception for {account.email}: {e}")
                import traceback
                traceback.print_exc()
                continue

        print(f"Tasks: Returning {len(all_task_lists)} task lists with tasks")
        # Sort lists by name by default
        all_task_lists.sort(key=lambda x: x["list_name"].lower())

        return all_task_lists

    def get_tasks_by_list_ordered(self, order: list[str] | None = None, account_id: UUID | None = None) -> list[dict[str, Any]]:
        """
        Get all tasks grouped by task list, with optional custom ordering.

        Args:
            order: Optional list of task list IDs specifying the desired order
            account_id: Optional UUID to filter tasks to a specific Google account.

        Returns:
            List of task list dictionaries, ordered according to the order parameter
        """
        task_lists = self.get_tasks_by_list(account_id=account_id)

        if order:
            # Create a mapping from list_id to list data
            lists_by_id = {tl["list_id"]: tl for tl in task_lists}

            # Build ordered list, starting with items in the specified order
            ordered = []
            for list_id in order:
                if list_id in lists_by_id:
                    ordered.append(lists_by_id.pop(list_id))

            # Append any remaining lists (new lists not in the order)
            ordered.extend(sorted(lists_by_id.values(), key=lambda x: x["list_name"].lower()))

            return ordered

        return task_lists

    def get_todays_tasks(self) -> list[dict[str, Any]]:
        """
        Get tasks due today or overdue from all connected accounts.
        Kept for backwards compatibility.

        Returns:
            List of task dictionaries
        """
        all_tasks = []
        task_lists = self.get_tasks_by_list()

        for task_list in task_lists:
            all_tasks.extend(task_list["tasks"])

        # Sort: priority tasks first, then by due date
        all_tasks.sort(key=lambda x: (not x["is_priority"], x["due_date"] or "9999-99-99"))

        return all_tasks

    def sync_tasks(self) -> dict[str, Any]:
        """
        Sync tasks from Google Tasks API.

        Returns:
            Dictionary with sync results:
            - success: Whether sync was successful
            - tasks_count: Number of tasks synced
            - lists_count: Number of task lists
            - error: Error message if any
        """
        try:
            task_lists = self.get_tasks_by_list()
            total_tasks = sum(len(tl["tasks"]) for tl in task_lists)
            return {
                "success": True,
                "tasks_count": total_tasks,
                "lists_count": len(task_lists),
                "error": None,
            }
        except Exception as e:
            return {
                "success": False,
                "tasks_count": 0,
                "lists_count": 0,
                "error": str(e),
            }

    def get_task(self, list_id: str, task_id: str) -> dict[str, Any] | None:
        """
        Get a single task by list ID and task ID.

        Args:
            list_id: The task list ID
            task_id: The task ID

        Returns:
            Dictionary with task data or None if not found
        """
        accounts = self.db.query(GoogleAccount).filter_by(is_active=True).all()
        local_tz = ZoneInfo("America/New_York")

        for account in accounts:
            try:
                credentials = self._get_credentials(account)
                service = build("tasks", "v1", credentials=credentials)

                # Get the task
                task = service.tasks().get(
                    tasklist=list_id,
                    task=task_id
                ).execute()

                # Get the list name
                try:
                    task_list = service.tasklists().get(tasklist=list_id).execute()
                    list_name = task_list.get("title", "Unknown List")
                except Exception:
                    list_name = "Unknown List"

                # Parse due date/time
                due_date = None
                due_time = None
                if task.get("due"):
                    due_str = task["due"]
                    try:
                        # Parse RFC 3339 format
                        due_dt = datetime.fromisoformat(due_str.replace("Z", "+00:00"))

                        # Check if this is a date-only task (midnight UTC)
                        is_date_only = (due_dt.hour == 0 and due_dt.minute == 0 and due_dt.second == 0)

                        if is_date_only:
                            # For date-only tasks, extract the date directly from UTC
                            # to avoid timezone shift issues
                            due_date = due_dt.strftime("%Y-%m-%d")
                            # No time for date-only tasks
                        else:
                            # Task has a specific time - convert to local timezone
                            due_local = due_dt.astimezone(local_tz)
                            due_date = due_local.strftime("%Y-%m-%d")
                            due_time = due_local.strftime("%H:%M")
                    except Exception:
                        pass

                return {
                    "id": task.get("id"),
                    "list_id": list_id,
                    "list_name": list_name,
                    "title": task.get("title", ""),
                    "notes": task.get("notes", ""),
                    "due_date": due_date,
                    "due_time": due_time,
                    "status": task.get("status"),
                    "completed": task.get("status") == "completed",
                }

            except HttpError as e:
                if e.resp.status == 404:
                    continue  # Task not found in this account, try next
                logger.error(f"Error getting task: {e}")
                continue
            except Exception as e:
                logger.error(f"Error getting task: {e}")
                continue

        return None

    def update_task(self, list_id: str, task_id: str, title: str | None = None, notes: str | None = None, due_date: str | None = None, due_time: str | None = None) -> dict[str, Any]:
        """
        Update a task's title, notes, and/or due date/time.

        Args:
            list_id: The task list ID
            task_id: The task ID
            title: New title (optional)
            notes: New notes (optional)
            due_date: New due date in YYYY-MM-DD format, or empty string to clear (optional)
            due_time: New due time in HH:MM format (24h), or empty string to clear (optional)

        Returns:
            Dictionary with success status and updated task data
        """
        accounts = self.db.query(GoogleAccount).filter_by(is_active=True).all()

        for account in accounts:
            try:
                credentials = self._get_credentials(account)
                service = build("tasks", "v1", credentials=credentials)

                # Build update body
                body = {}
                if title is not None:
                    body["title"] = title
                if notes is not None:
                    body["notes"] = notes

                # Handle due date/time - Google Tasks expects RFC 3339 format
                if due_date is not None:
                    if due_date == "" or due_date is None:
                        # Clear the due date
                        body["due"] = None
                    else:
                        # Check if time is provided
                        if due_time and due_time.strip():
                            # Combine date and time, convert from local to UTC
                            local_tz = ZoneInfo("America/New_York")
                            due_dt = datetime.strptime(f"{due_date} {due_time}", "%Y-%m-%d %H:%M")
                            due_dt = due_dt.replace(tzinfo=local_tz)
                            body["due"] = due_dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
                        else:
                            # Date only: Use noon local time to avoid timezone day-shift issues
                            # Google Tasks will display this as an all-day task on the correct date
                            local_tz = ZoneInfo("America/New_York")
                            due_dt = datetime.strptime(f"{due_date} 12:00", "%Y-%m-%d %H:%M")
                            due_dt = due_dt.replace(tzinfo=local_tz)
                            body["due"] = due_dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

                if not body:
                    return {"success": False, "error": "No updates provided"}

                # Update the task
                result = service.tasks().patch(
                    tasklist=list_id,
                    task=task_id,
                    body=body
                ).execute()

                return {
                    "success": True,
                    "task": {
                        "id": result.get("id"),
                        "title": result.get("title"),
                        "notes": result.get("notes"),
                        "due": result.get("due"),
                    }
                }

            except HttpError as e:
                if e.resp.status == 404:
                    continue  # Task not found in this account, try next
                return {"success": False, "error": str(e)}
            except Exception as e:
                continue

        return {"success": False, "error": "Task not found"}

    def toggle_task(self, list_id: str, task_id: str) -> dict[str, Any]:
        """
        Toggle a task's completion status.

        Args:
            list_id: The task list ID
            task_id: The task ID

        Returns:
            Dictionary with success status and new completion state
        """
        accounts = self.db.query(GoogleAccount).filter_by(is_active=True).all()

        for account in accounts:
            try:
                credentials = self._get_credentials(account)
                service = build("tasks", "v1", credentials=credentials)

                # First, get the current task to check its status
                task = service.tasks().get(tasklist=list_id, task=task_id).execute()
                current_status = task.get("status", "needsAction")

                # Toggle the status
                new_status = "completed" if current_status == "needsAction" else "needsAction"

                # Update the task
                result = service.tasks().patch(
                    tasklist=list_id,
                    task=task_id,
                    body={"status": new_status}
                ).execute()

                return {
                    "success": True,
                    "completed": new_status == "completed",
                }

            except HttpError as e:
                if e.resp.status == 404:
                    continue  # Task not found in this account, try next
                return {"success": False, "error": str(e)}
            except Exception as e:
                continue

        return {"success": False, "error": "Task not found"}

    def create_task(self, list_id: str, title: str, notes: str | None = None, due_date: str | None = None, due_time: str | None = None, parent_task_id: str | None = None) -> dict[str, Any]:
        """
        Create a new task in the specified list.

        Args:
            list_id: The task list ID
            title: Task title
            notes: Task notes/description (optional)
            due_date: Due date in YYYY-MM-DD format (optional)
            due_time: Due time in HH:MM format (24h, optional)
            parent_task_id: Parent task ID to create as subtask (optional)

        Returns:
            Dictionary with success status and created task data
        """
        accounts = self.db.query(GoogleAccount).filter_by(is_active=True).all()

        for account in accounts:
            try:
                credentials = self._get_credentials(account)
                service = build("tasks", "v1", credentials=credentials)

                # Verify the list exists for this account
                try:
                    service.tasklists().get(tasklist=list_id).execute()
                except HttpError as e:
                    if e.resp.status == 404:
                        continue  # List not found in this account, try next
                    raise

                # Build task body
                body = {"title": title}
                if notes:
                    body["notes"] = notes
                if due_date:
                    if due_time and due_time.strip():
                        # Combine date and time, convert from local to UTC
                        local_tz = ZoneInfo("America/New_York")
                        due_dt = datetime.strptime(f"{due_date} {due_time}", "%Y-%m-%d %H:%M")
                        due_dt = due_dt.replace(tzinfo=local_tz)
                        body["due"] = due_dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
                    else:
                        # Date only: Use noon local time to avoid timezone day-shift issues
                        # Google Tasks will display this as an all-day task on the correct date
                        local_tz = ZoneInfo("America/New_York")
                        due_dt = datetime.strptime(f"{due_date} 12:00", "%Y-%m-%d %H:%M")
                        due_dt = due_dt.replace(tzinfo=local_tz)
                        body["due"] = due_dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

                # Create the task (with optional parent for subtasks)
                insert_kwargs = {
                    "tasklist": list_id,
                    "body": body,
                }
                if parent_task_id:
                    insert_kwargs["parent"] = parent_task_id

                result = service.tasks().insert(**insert_kwargs).execute()

                return {
                    "success": True,
                    "task": {
                        "id": result.get("id"),
                        "title": result.get("title"),
                        "notes": result.get("notes"),
                        "due": result.get("due"),
                    }
                }

            except HttpError as e:
                return {"success": False, "error": str(e)}
            except Exception as e:
                continue

        return {"success": False, "error": "Could not create task - no valid account found"}

    def move_task(
        self,
        source_list_id: str,
        task_id: str,
        target_list_id: str,
        previous_task_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Move a task to a different list.

        Google Tasks API doesn't support moving between lists directly,
        so we need to: get the task, create it in target, delete from source.

        Args:
            source_list_id: The source task list ID
            task_id: The task ID to move
            target_list_id: The target task list ID
            previous_task_id: Insert after this task ID (optional, for ordering)

        Returns:
            Dictionary with success status
        """
        accounts = self.db.query(GoogleAccount).filter_by(is_active=True).all()

        for account in accounts:
            try:
                credentials = self._get_credentials(account)
                service = build("tasks", "v1", credentials=credentials)

                # Get the task from source list
                try:
                    task = service.tasks().get(
                        tasklist=source_list_id,
                        task=task_id
                    ).execute()
                except HttpError as e:
                    if e.resp.status == 404:
                        continue  # Not found in this account
                    raise

                # If moving to the same list, just reorder
                if source_list_id == target_list_id:
                    # Use move API for reordering within same list
                    result = service.tasks().move(
                        tasklist=source_list_id,
                        task=task_id,
                        previous=previous_task_id if previous_task_id else None,
                    ).execute()
                    return {"success": True, "task_id": result.get("id")}

                # Moving to different list: create in target, delete from source
                # Build new task body (preserve all fields except id)
                new_task = {
                    "title": task.get("title", ""),
                    "notes": task.get("notes"),
                    "due": task.get("due"),
                    "status": task.get("status", "needsAction"),
                }

                # Create in target list
                created = service.tasks().insert(
                    tasklist=target_list_id,
                    body=new_task,
                    previous=previous_task_id if previous_task_id else None,
                ).execute()

                # Delete from source list
                service.tasks().delete(
                    tasklist=source_list_id,
                    task=task_id
                ).execute()

                return {
                    "success": True,
                    "task_id": created.get("id"),
                    "moved_to": target_list_id,
                }

            except HttpError as e:
                return {"success": False, "error": str(e)}
            except Exception as e:
                continue

        return {"success": False, "error": "Task not found"}


def get_tasks_service(db: Session) -> TasksService:
    """Get a Tasks service instance."""
    return TasksService(db)
