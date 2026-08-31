"""
Firestore database services for Cognitive Canvas.
Provides direct, clean, and reliable CRUD operations for projects, tasks, and research.
"""

from typing import Optional, List, Dict, Any
from google.cloud import firestore

# Initialize Firestore Client
db = firestore.Client(project="negnq-agenticassistant")


# ─── Task Services ─────────────────────────────────────────────────────────────

def create_task(
    title: str,
    due_date: Optional[str] = None,
    priority: str = "medium",
    task_type: str = "task",
    details: str = "",
    project_id: Optional[str] = None,
    estimated_minutes: Optional[int] = None,
    depends_on: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Creates a new task in Firestore.

    Args:
        title: Short, descriptive title of the task.
        due_date: ISO date formatted string YYYY-MM-DD (e.g. '2026-09-14') or None.
        priority: 'high', 'medium', or 'low'.
        task_type: 'task', 'study', 'reading', 'event', 'meeting', 'reminder', etc.
        details: Additional context, notes, or instructions.
        project_id: ID of parent project if part of one, else None or 'unassigned'.
        estimated_minutes: Estimated duration in minutes (e.g. 30, 60, 120).
        depends_on: Optional list of prerequisite task IDs.
    """
    task_ref = db.collection("tasks").document()
    
    clean_project_id = project_id if (project_id and project_id != "unassigned") else None

    task_data = {
        "title": title.strip(),
        "due_date": due_date.strip() if due_date else None,
        "priority": priority.lower() if priority in ["high", "medium", "low"] else "medium",
        "task_type": task_type.lower(),
        "details": details.strip() if details else "",
        "project_id": clean_project_id,
        "status": "queued",
        "estimated_minutes": estimated_minutes,
        "depends_on": depends_on or [],
        "created_at": firestore.SERVER_TIMESTAMP,
    }

    task_ref.set(task_data)
    
    return {
        "task_id": task_ref.id,
        "title": task_data["title"],
        "due_date": task_data["due_date"],
        "priority": task_data["priority"],
        "status": "queued",
        "project_id": clean_project_id,
    }


def get_task(task_id: str) -> Optional[Dict[str, Any]]:
    """Fetches a single task by ID."""
    doc = db.collection("tasks").document(task_id).get()
    if not doc.exists:
        return None
    return {"id": doc.id, **doc.to_dict()}


def update_task(task_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """
    Updates fields of an existing task.
    Allowed fields: title, due_date, priority, status, details, estimated_minutes, project_id.
    """
    allowed_fields = {
        "title",
        "due_date",
        "priority",
        "status",
        "details",
        "estimated_minutes",
        "project_id",
    }
    
    safe_updates = {k: v for k, v in updates.items() if k in allowed_fields and v is not None}
    
    if "status" in safe_updates and safe_updates["status"] == "completed":
        safe_updates["completed_at"] = firestore.SERVER_TIMESTAMP
        
    task_ref = db.collection("tasks").document(task_id)
    doc = task_ref.get()
    if not doc.exists:
        raise ValueError(f"Task with ID {task_id} not found.")

    if safe_updates:
        task_ref.update(safe_updates)

    return {"task_id": task_id, "updated_fields": list(safe_updates.keys()), "status": "success"}


def delete_task(task_id: str) -> Dict[str, Any]:
    """Deletes a task by ID."""
    task_ref = db.collection("tasks").document(task_id)
    doc = task_ref.get()
    if not doc.exists:
        return {"task_id": task_id, "status": "not_found"}
    task_ref.delete()
    return {"task_id": task_id, "status": "deleted"}


def list_tasks(
    project_id: Optional[str] = None,
    due_date: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """Queries tasks with optional filters."""
    query = db.collection("tasks")
    
    if project_id:
        query = query.where("project_id", "==", project_id)
    if due_date:
        query = query.where("due_date", "==", due_date)
    if status:
        query = query.where("status", "==", status)
        
    docs = query.limit(limit).stream()
    return [{"id": d.id, **d.to_dict()} for d in docs]


def batch_create_tasks(
    project_id: str,
    tasks: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Creates multiple tasks for a project in batch.
    Each item in tasks is a dict with title, due_date, priority, details, estimated_minutes, etc.
    """
    created = []
    batch = db.batch()
    
    for t in tasks:
        task_ref = db.collection("tasks").document()
        task_data = {
            "project_id": project_id,
            "title": t.get("title", "Untitled Task").strip(),
            "due_date": t.get("due_date"),
            "priority": t.get("priority", "medium").lower(),
            "task_type": t.get("task_type", "task").lower(),
            "details": t.get("details", ""),
            "status": "queued",
            "estimated_minutes": t.get("estimated_minutes"),
            "depends_on": t.get("depends_on", []),
            "created_at": firestore.SERVER_TIMESTAMP,
        }
        batch.set(task_ref, task_data)
        created.append({
            "task_id": task_ref.id,
            "title": task_data["title"],
            "due_date": task_data["due_date"],
            "priority": task_data["priority"],
            "estimated_minutes": task_data["estimated_minutes"],
        })
        
    batch.commit()
    return created


# ─── Project Services ──────────────────────────────────────────────────────────

def create_project(
    title: str,
    summary: str = "",
    deadline: Optional[str] = None,
) -> Dict[str, Any]:
    """Creates a new project in Firestore."""
    project_ref = db.collection("projects").document()
    
    project_data = {
        "title": title.strip(),
        "summary": summary.strip() if summary else "",
        "deadline": deadline.strip() if deadline else None,
        "status": "active",
        "created_at": firestore.SERVER_TIMESTAMP,
    }
    
    project_ref.set(project_data)
    
    return {
        "project_id": project_ref.id,
        "title": project_data["title"],
        "summary": project_data["summary"],
        "deadline": project_data["deadline"],
        "status": "active",
    }


def get_project(project_id: str) -> Optional[Dict[str, Any]]:
    """Fetches a single project by ID."""
    doc = db.collection("projects").document(project_id).get()
    if not doc.exists:
        return None
    return {"id": doc.id, **doc.to_dict()}


def list_projects(status: Optional[str] = None) -> List[Dict[str, Any]]:
    """Queries all projects."""
    query = db.collection("projects")
    if status:
        query = query.where("status", "==", status)
    docs = query.stream()
    return [{"id": d.id, **d.to_dict()} for d in docs]


def update_project(project_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """Updates fields of an existing project (title, summary, deadline, status)."""
    allowed_fields = {"title", "summary", "deadline", "status"}
    safe_updates = {k: v for k, v in updates.items() if k in allowed_fields and v is not None}
    
    project_ref = db.collection("projects").document(project_id)
    doc = project_ref.get()
    if not doc.exists:
        raise ValueError(f"Project with ID {project_id} not found.")

    if safe_updates:
        project_ref.update(safe_updates)

    return {"project_id": project_id, "updated_fields": list(safe_updates.keys()), "status": "success"}


def delete_project(project_id: str, cascade_tasks: bool = True) -> Dict[str, Any]:
    """
    Deletes a project from Firestore.
    If cascade_tasks is True, also deletes all associated tasks and research notes.
    """
    project_ref = db.collection("projects").document(project_id)
    doc = project_ref.get()
    if not doc.exists:
        return {"project_id": project_id, "status": "not_found"}

    deleted_tasks_count = 0
    deleted_notes_count = 0

    if cascade_tasks:
        # Delete associated tasks
        task_docs = db.collection("tasks").where("project_id", "==", project_id).stream()
        batch = db.batch()
        for t_doc in task_docs:
            batch.delete(t_doc.reference)
            deleted_tasks_count += 1
        
        # Delete associated research notes
        research_docs = db.collection("research_results").where("project_id", "==", project_id).stream()
        for r_doc in research_docs:
            batch.delete(r_doc.reference)
            deleted_notes_count += 1
            
        batch.commit()

    # Delete project document
    project_ref.delete()

    return {
        "project_id": project_id,
        "deleted_tasks_count": deleted_tasks_count,
        "deleted_notes_count": deleted_notes_count,
        "status": "deleted",
    }


# ─── Research Services ─────────────────────────────────────────────────────────

def save_research_result(
    query: str,
    summary: str,
    project_id: Optional[str] = None,
    source_type: str = "web_search",
) -> Dict[str, Any]:
    """Saves a research finding to Firestore."""
    ref = db.collection("research_results").document()
    data = {
        "query": query,
        "summary": summary,
        "project_id": project_id,
        "source_type": source_type,
        "status": "COMPLETED",
        "created_at": firestore.SERVER_TIMESTAMP,
    }
    ref.set(data)
    return {"result_id": ref.id, "query": query, "status": "saved"}


def delete_research_result(result_id: str) -> Dict[str, Any]:
    """Deletes a research result finding by ID."""
    ref = db.collection("research_results").document(result_id)
    doc = ref.get()
    if not doc.exists:
        return {"result_id": result_id, "status": "not_found"}
    ref.delete()
    return {"result_id": result_id, "status": "deleted"}