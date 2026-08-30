from google.cloud import firestore
from .event_services import create_event


db = firestore.Client(project="negnq-agenticassistant")

def save_event(event: dict) -> str:
    event_id = event["event_id"]

    db.collection("events").document(event_id).set({
        **event,
        "status": "PENDING",
        "processed": False,
        "attempt_count": 0,
        "max_attempts": 3,
    })

    return event_id

def save_research_result(
    event_id: str,
    project_id: str | None,
    query: str,
    summary: str,
    source_type: str,
) -> str:

    result_ref = db.collection("research_results").document()

    result_ref.set({
        "event_id": event_id,
        "project_id": project_id,
        "query": query,
        "summary": summary,
        "source_type": source_type,
        "status": "COMPLETED",
        "created_at": firestore.SERVER_TIMESTAMP,
    })

    return result_ref.id

def get_task(task_id: str) -> dict | None:
    doc = db.collection("tasks").document(task_id).get()

    if not doc.exists:
        return None

    return {
        "id": doc.id,
        **doc.to_dict(),
    }


def list_project_tasks(project_id: str) -> list[dict]:
    docs = (
        db.collection("tasks")
        .where("project_id", "==", project_id)
        .stream()
    )

    return [
        {
            "id": doc.id,
            **doc.to_dict(),
        }
        for doc in docs
    ]


def update_task(task_id: str, updates: dict) -> str:
    allowed_fields = {
        "title",
        "priority",
        "due_date",
        "details",
        "status",
    }

    safe_updates = {
        key: value
        for key, value in updates.items()
        if key in allowed_fields
    }

    if not safe_updates:
        return "No valid fields to update."

    db.collection("tasks").document(task_id).update(safe_updates)

    return f"Task {task_id} updated successfully."

def create_task(
    project_id: str,
    title: str,
    task_type: str,
    priority: str = "medium",
    due_date: str | None = None,
    details: str = "",
    create_event_for_task: bool = False,
    source_event_id: str | None = None,
) -> str:
    """
    Create a task in Firestore.

    By default, task creation does not emit a TASK_CREATED event.
    This prevents agent-created subtasks from recursively triggering
    the event dispatcher.
    """

    existing = (
        db.collection("tasks")
        .where("project_id", "==", project_id)
        .where("title", "==", title)
        .limit(1)
        .stream()
    )

    if next(existing, None):
        return "Task already exists."

    task_ref = db.collection("tasks").document()

    task_ref.set({
        "project_id": project_id,
        "title": title,
        "task_type": task_type,
        "priority": priority,
        "due_date": due_date,
        "details": details,
        "status": "queued",
        "source_event_id": source_event_id,
    })

    if create_event_for_task:
        event = create_event(
            "TASK_CREATED",
            task_ref.id,
            {
                "project_id": project_id,
                "task_title": title,
                "task_type": task_type,
            },
        )

        save_event(event)

    return task_ref.id

def save_extraction(extraction: dict) -> str:
    """
    Persist an extraction according to its intent.

    task     -> create tasks + TASK_CREATED events
    plan     -> create project + PLAN_REQUESTED event
    research -> create RESEARCH_REQUESTED event
    """

    intent = extraction.get("intent", "task")

    # ---------------------------------------------------------
    # TASK
    # ---------------------------------------------------------
    if intent == "task":

        project_ref = db.collection("projects").document()

        project_ref.set({
            "title": extraction.get("project_title"),
            "summary": extraction.get("summary", ""),
            "deadline": extraction.get("project_deadline"),
            "status": "active",
        })

        project_id = project_ref.id

        for task in extraction.get("tasks", []):
            task_ref = db.collection("tasks").document()

            task_ref.set({
                "project_id": project_id,
                "title": task["title"],
                "task_type": task["task_type"],
                "priority": task["priority"],
                "due_date": task.get("due_date"),
                "details": task.get("details", ""),
                "status": "queued",
            })

            event = create_event(
                "TASK_CREATED",
                task_ref.id,
                {
                    "project_id": project_id,
                    "task_title": task["title"],
                    "task_type": task["task_type"],
                },
            )

            save_event(event)

            print("EVENT SAVED:", event)

        return (
            f"Saved project {project_id} with "
            f"{len(extraction.get('tasks', []))} tasks."
        )

    # ---------------------------------------------------------
    # PLAN
    # ---------------------------------------------------------
    if intent == "plan":

        project_ref = db.collection("projects").document()

        project_ref.set({
            "title": extraction.get("project_title"),
            "summary": extraction.get("summary", ""),
            "deadline": extraction.get("project_deadline"),
            "status": "active",
        })

        project_id = project_ref.id

        event = create_event(
            "PLAN_REQUESTED",
            project_id,
            {
                "project_id": project_id,
                "goal": extraction.get("summary", ""),
                "deadline": extraction.get("project_deadline"),
            },
        )

        save_event(event)

        print("EVENT SAVED:", event)

        return f"Created project {project_id} and requested a plan."

    # ---------------------------------------------------------
    # RESEARCH
    # ---------------------------------------------------------
    if intent == "research":

        project_ref = db.collection("projects").document()

        project_ref.set({
            "title": extraction.get("project_title"),
            "summary": extraction.get("summary", ""),
            "deadline": extraction.get("project_deadline"),
            "status": "active",
        })

        project_id = project_ref.id

        event = create_event(
            "RESEARCH_REQUESTED",
            project_id,
            {
                "project_id": project_id,
                "query": extraction.get("summary", ""),
                "project_title": extraction.get("project_title"),
                "project_deadline": extraction.get("project_deadline"),
            },
        )

        save_event(event)

        print("EVENT SAVED:", event)

        return f"Created project {project_id} and requested research."

    # ---------------------------------------------------------
    # UNKNOWN INTENT
    # ---------------------------------------------------------
    raise ValueError(f"Unsupported extraction intent: {intent}")

def has_tasks_for_event(source_event_id: str) -> bool:
    docs = (
        db.collection("tasks")
        .where("source_event_id", "==", source_event_id)
        .limit(1)
        .stream()
    )

    return next(docs, None) is not None