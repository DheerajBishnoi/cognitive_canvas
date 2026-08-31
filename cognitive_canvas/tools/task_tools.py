"""
Task management tools for the Cognitive Canvas Agent.
Callable directly by Gemini via Google ADK function calling.
"""

from typing import Optional, List
from cognitive_canvas.services.firestore_services import (
    create_task as db_create_task,
    update_task as db_update_task,
    delete_task as db_delete_task,
    list_tasks as db_list_tasks,
    get_task as db_get_task,
)


def create_task(
    title: str,
    due_date: Optional[str] = None,
    priority: str = "medium",
    task_type: str = "task",
    details: str = "",
    project_id: Optional[str] = None,
    estimated_minutes: Optional[int] = None,
) -> str:
    """Creates a new standalone task or scheduled event in the calendar.

    Use this for single activities, meetings, deadlines, movie dates, reminders,
    or standalone study items that do NOT require creating an entire multi-week project.

    Args:
        title: Clear title of the task (e.g. 'Movie date with Sarah', 'Review Chapter 3', 'Dentist appointment').
        due_date: Target date formatted as ISO string YYYY-MM-DD (e.g. '2026-09-14'). If no date specified, pass None.
        priority: Priority level: 'high', 'medium', or 'low'. Defaults to 'medium'.
        task_type: Type of task (e.g. 'task', 'study', 'event', 'reminder', 'meeting', 'reading').
        details: Optional additional notes, links, or context.
        project_id: Optional parent project ID if this task belongs to an existing project.
        estimated_minutes: Optional estimated duration in minutes (e.g. 30, 60, 90).

    Returns:
        Confirmation message with task details and generated task ID.
    """
    try:
        res = db_create_task(
            title=title,
            due_date=due_date,
            priority=priority,
            task_type=task_type,
            details=details,
            project_id=project_id,
            estimated_minutes=estimated_minutes,
        )
        date_str = f" scheduled for {res['due_date']}" if res.get('due_date') else " (no due date)"
        return f"✅ Created task '{res['title']}'{date_str} (Priority: {res['priority']}). Task ID: {res['task_id']}"
    except Exception as e:
        return f"❌ Failed to create task: {str(e)}"


def update_task(
    task_id: str,
    title: Optional[str] = None,
    due_date: Optional[str] = None,
    priority: Optional[str] = None,
    status: Optional[str] = None,
    details: Optional[str] = None,
    estimated_minutes: Optional[int] = None,
) -> str:
    """Updates an existing task's title, due date, status, priority, or details.

    Use this when the user wants to mark a task as completed ('completed'), reschedule a task to another date,
    change priority, or edit task information.

    Args:
        task_id: The ID of the task to update.
        title: Optional updated title.
        due_date: Optional updated date in YYYY-MM-DD format.
        priority: Optional updated priority ('high', 'medium', 'low').
        status: Optional updated status ('completed', 'queued', 'in-progress').
        details: Optional updated notes or details.
        estimated_minutes: Optional updated duration in minutes.

    Returns:
        Confirmation message of the updated fields.
    """
    try:
        updates = {}
        if title is not None: updates["title"] = title
        if due_date is not None: updates["due_date"] = due_date
        if priority is not None: updates["priority"] = priority
        if status is not None: updates["status"] = status
        if details is not None: updates["details"] = details
        if estimated_minutes is not None: updates["estimated_minutes"] = estimated_minutes

        if not updates:
            return f"No update parameters were provided for task {task_id}."

        res = db_update_task(task_id, updates)
        return f"✅ Task {task_id} updated successfully: {', '.join(res['updated_fields'])}."
    except Exception as e:
        return f"❌ Failed to update task {task_id}: {str(e)}"


def delete_task(task_id: str) -> str:
    """Deletes a task from the system.

    Args:
        task_id: The ID of the task to remove.

    Returns:
        Confirmation of task deletion.
    """
    try:
        res = db_delete_task(task_id)
        if res["status"] == "not_found":
            return f"Task with ID {task_id} was not found."
        return f"✅ Task {task_id} has been deleted."
    except Exception as e:
        return f"❌ Failed to delete task {task_id}: {str(e)}"


def list_tasks(
    project_id: Optional[str] = None,
    due_date: Optional[str] = None,
    status: Optional[str] = None,
) -> str:
    """Queries existing tasks to check what is scheduled or in progress.

    Args:
        project_id: Optional project ID to filter by.
        due_date: Optional ISO date string (YYYY-MM-DD) to see tasks on that date.
        status: Optional status filter ('queued', 'completed', 'in-progress').

    Returns:
        Formatted summary list of matching tasks.
    """
    try:
        tasks = db_list_tasks(project_id=project_id, due_date=due_date, status=status)
        if not tasks:
            return "No tasks found matching the criteria."

        lines = [f"Found {len(tasks)} task(s):"]
        for t in tasks:
            status_emoji = "✓" if t.get("status") == "completed" else "○"
            due_str = f" [Due: {t.get('due_date')}]" if t.get("due_date") else ""
            prio_str = f" [{t.get('priority', 'medium').upper()}]"
            lines.append(f"- {status_emoji} (ID: {t['id']}) {t.get('title')}{due_str}{prio_str}")
        return "\n".join(lines)
    except Exception as e:
        return f"❌ Failed to list tasks: {str(e)}"
