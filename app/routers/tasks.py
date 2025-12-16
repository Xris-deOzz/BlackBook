"""
Tasks router for Google Tasks integration.

Provides endpoints for syncing and managing Google Tasks.
"""

import json
from typing import Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Setting

router = APIRouter(prefix="/tasks", tags=["tasks"])


class TaskUpdate(BaseModel):
    """Request model for updating a task."""
    title: Optional[str] = None
    notes: Optional[str] = None
    due_date: Optional[str] = None  # Format: YYYY-MM-DD or null to clear


class ListOrderUpdate(BaseModel):
    """Request model for updating task list order."""
    order: list[str]


class TaskCreate(BaseModel):
    """Request model for creating a new task."""
    title: str
    notes: Optional[str] = None
    due_date: Optional[str] = None  # Format: YYYY-MM-DD


@router.post("/sync", response_class=HTMLResponse)
async def sync_tasks(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Sync tasks from Google Tasks API.

    Returns HTML partial with sync status.
    """
    try:
        from app.services.tasks_service import get_tasks_service

        tasks_service = get_tasks_service(db)
        result = tasks_service.sync_tasks()

        if result["success"]:
            return HTMLResponse(
                content=f"""
                <span class="text-green-600 text-xs">
                    Synced {result['tasks_count']} tasks
                </span>
                <script>
                    // Refresh tasks widget after sync
                    setTimeout(function() {{
                        htmx.ajax('GET', '/dashboard/tasks-widget', '#todays-tasks');
                    }}, 500);
                </script>
                """,
                status_code=200,
            )
        else:
            return HTMLResponse(
                content=f'<span class="text-red-600 text-xs">Sync failed: {result["error"]}</span>',
                status_code=200,
            )
    except ImportError:
        return HTMLResponse(
            content='<span class="text-yellow-600 text-xs">Tasks service not available</span>',
            status_code=200,
        )
    except Exception as e:
        return HTMLResponse(
            content=f'<span class="text-red-600 text-xs">Error: {str(e)}</span>',
            status_code=200,
        )


@router.patch("/{list_id}/{task_id}")
async def update_task(
    list_id: str,
    task_id: str,
    task_update: TaskUpdate,
    db: Session = Depends(get_db),
):
    """
    Update a task's title and/or notes.

    Args:
        list_id: The task list ID
        task_id: The task ID
        task_update: The update data (title and/or notes)

    Returns:
        JSON response with success status
    """
    try:
        from app.services.tasks_service import get_tasks_service

        tasks_service = get_tasks_service(db)
        result = tasks_service.update_task(
            list_id=list_id,
            task_id=task_id,
            title=task_update.title,
            notes=task_update.notes,
            due_date=task_update.due_date,
        )

        if result["success"]:
            return JSONResponse(content=result, status_code=200)
        else:
            return JSONResponse(content=result, status_code=400)

    except Exception as e:
        return JSONResponse(
            content={"success": False, "error": str(e)},
            status_code=500,
        )


@router.post("/{list_id}/{task_id}/toggle")
async def toggle_task(
    list_id: str,
    task_id: str,
    db: Session = Depends(get_db),
):
    """
    Toggle a task's completion status.

    Args:
        list_id: The task list ID
        task_id: The task ID

    Returns:
        JSON response with success status and new completion state
    """
    try:
        from app.services.tasks_service import get_tasks_service

        tasks_service = get_tasks_service(db)
        result = tasks_service.toggle_task(list_id=list_id, task_id=task_id)

        if result["success"]:
            return JSONResponse(content=result, status_code=200)
        else:
            return JSONResponse(content=result, status_code=400)

    except Exception as e:
        return JSONResponse(
            content={"success": False, "error": str(e)},
            status_code=500,
        )


@router.post("/{list_id}")
async def create_task(
    list_id: str,
    task_create: TaskCreate,
    db: Session = Depends(get_db),
):
    """
    Create a new task in the specified list.

    Args:
        list_id: The task list ID
        task_create: Task creation data (title, notes, due_date)

    Returns:
        JSON response with success status and created task data
    """
    try:
        from app.services.tasks_service import get_tasks_service

        tasks_service = get_tasks_service(db)
        result = tasks_service.create_task(
            list_id=list_id,
            title=task_create.title,
            notes=task_create.notes,
            due_date=task_create.due_date,
        )

        if result["success"]:
            return JSONResponse(content=result, status_code=201)
        else:
            return JSONResponse(content=result, status_code=400)

    except Exception as e:
        return JSONResponse(
            content={"success": False, "error": str(e)},
            status_code=500,
        )


@router.post("/reorder-lists")
async def reorder_task_lists(
    order_update: ListOrderUpdate,
    db: Session = Depends(get_db),
):
    """
    Save the user's preferred task list order.

    This is stored locally and applied when displaying task lists.
    Google Tasks API doesn't support reordering task lists,
    so we store the order preference in our database.

    Args:
        order_update: List of task list IDs in the desired order

    Returns:
        JSON response with success status
    """
    try:
        # Store the order in settings
        setting = db.query(Setting).filter_by(key="task_list_order").first()
        order_json = json.dumps(order_update.order)

        if setting:
            setting.value = order_json
        else:
            setting = Setting(key="task_list_order", value=order_json)
            db.add(setting)

        db.commit()

        return JSONResponse(
            content={"success": True, "order": order_update.order},
            status_code=200,
        )

    except Exception as e:
        db.rollback()
        return JSONResponse(
            content={"success": False, "error": str(e)},
            status_code=500,
        )
