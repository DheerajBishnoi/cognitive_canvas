"""
Project management and multi-step planning tools for the Cognitive Canvas Agent.
Callable directly by Gemini via Google ADK function calling.
"""

from typing import Optional, List, Dict, Any
from cognitive_canvas.services.firestore_services import (
    create_project as db_create_project,
    get_project as db_get_project,
    list_projects as db_list_projects,
    batch_create_tasks as db_batch_create_tasks,
)


def create_project(
    title: str,
    summary: str = "",
    deadline: Optional[str] = None,
) -> str:
    """Creates a new high-level Project container.

    Use this ONLY for comprehensive multi-day or multi-week initiatives, structured learning curriculums,
    or exam preparations (e.g. 'Operating Systems Exam Prep', 'Learn Python in 30 Days', 'Devpost Hackathon Submission').
    Do NOT call this for single standalone tasks, reminders, or single-day events.

    Args:
        title: Title of the project (e.g. 'Operating Systems Study Plan').
        summary: High-level overview or goal description of the project.
        deadline: Target completion date in ISO format YYYY-MM-DD (e.g. '2026-09-15') if specified.

    Returns:
        Confirmation message with Project ID and details.
    """
    try:
        res = db_create_project(title=title, summary=summary, deadline=deadline)
        dl_str = f" with deadline {res['deadline']}" if res.get('deadline') else ""
        return f"✅ Created Project '{res['title']}'{dl_str}. Project ID: {res['project_id']}"
    except Exception as e:
        return f"❌ Failed to create project: {str(e)}"


def plan_project_tasks(
    project_id: str,
    tasks: List[Dict[str, Any]],
) -> str:
    """Batch-creates a sequence of dated, actionable tasks under an existing Project.

    Call this after creating a project (or for an existing project) to populate its actionable roadmap.

    Args:
        project_id: The ID of the parent project created via create_project.
        tasks: A list of task dictionaries to create. Each task dictionary should have:
            - title (str, required): Specific, actionable task name (e.g. 'Read Chapter 1: Processes & Threads')
            - due_date (str, optional): Scheduled date formatted as 'YYYY-MM-DD'
            - priority (str, optional): 'high', 'medium', or 'low' (defaults to 'medium')
            - task_type (str, optional): 'study', 'reading', 'practice', 'review', etc.
            - estimated_minutes (int, optional): Duration in minutes (e.g. 60, 90)
            - details (str, optional): Specific subtopics, page numbers, or instructions

    Returns:
        Confirmation of how many tasks were successfully scheduled under the project.
    """
    try:
        if not tasks:
            return "No tasks provided to plan."

        created = db_batch_create_tasks(project_id=project_id, tasks=tasks)
        
        lines = [f"✅ Successfully scheduled {len(created)} task(s) for Project {project_id}:"]
        for t in created:
            date_str = f" (Date: {t['due_date']})" if t.get('due_date') else ""
            lines.append(f"- '{t['title']}'{date_str} [{t['priority'].upper()}]")
        return "\n".join(lines)
    except Exception as e:
        return f"❌ Failed to schedule tasks for project {project_id}: {str(e)}"


def update_project(
    project_id: str,
    title: Optional[str] = None,
    summary: Optional[str] = None,
    deadline: Optional[str] = None,
    status: Optional[str] = None,
) -> str:
    """Updates an existing project's title, summary, deadline, or status.

    Args:
        project_id: The ID of the project to update.
        title: Optional new project title.
        summary: Optional new overview/summary.
        deadline: Optional new deadline in YYYY-MM-DD format.
        status: Optional status ('active', 'completed', 'archived').

    Returns:
        Confirmation of updated project fields.
    """
    try:
        from cognitive_canvas.services.firestore_services import update_project as db_update_project
        updates = {}
        if title is not None: updates["title"] = title
        if summary is not None: updates["summary"] = summary
        if deadline is not None: updates["deadline"] = deadline
        if status is not None: updates["status"] = status

        if not updates:
            return f"No update parameters provided for project {project_id}."

        res = db_update_project(project_id, updates)
        return f"✅ Project {project_id} updated successfully: {', '.join(res['updated_fields'])}."
    except Exception as e:
        return f"❌ Failed to update project {project_id}: {str(e)}"


def delete_project(project_id: str) -> str:
    """Permanently deletes a project container and all of its associated tasks and research notes.

    Use this when the user asks to delete, remove, or clear an entire project.

    Args:
        project_id: The ID of the project to delete.

    Returns:
        Confirmation of project and task deletion.
    """
    try:
        from cognitive_canvas.services.firestore_services import delete_project as db_delete_project
        res = db_delete_project(project_id, cascade_tasks=True)
        if res["status"] == "not_found":
            return f"Project with ID {project_id} was not found."
        return f"✅ Project {project_id} and all its {res.get('deleted_tasks_count', 0)} task(s) have been permanently deleted."
    except Exception as e:
        return f"❌ Failed to delete project {project_id}: {str(e)}"


def list_projects() -> str:
    """Lists all existing projects and their statuses.

    Returns:
        Summary of all active projects in the system.
    """
    try:
        projs = db_list_projects()
        if not projs:
            return "No active projects found in the system."
        
        lines = [f"Found {len(projs)} project(s):"]
        for p in projs:
            dl_str = f" [Deadline: {p.get('deadline')}]" if p.get('deadline') else ""
            lines.append(f"- (ID: {p['id']}) {p.get('title')}{dl_str} - Status: {p.get('status', 'active')}")
        return "\n".join(lines)
    except Exception as e:
        return f"❌ Failed to list projects: {str(e)}"
