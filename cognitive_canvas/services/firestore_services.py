from google.cloud import firestore
from .event_services import create_event


db = firestore.Client(project="negnq-agenticassistant")

def save_event(event: dict) -> str:
    event_id = event["event_id"]

    db.collection("events").document(event_id).set({
        **event,
        "processed": False,
    })

    return event_id

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

def save_extraction(extraction: dict) -> str:
    """
    Saves an extracted project and its tasks to Firestore.
    """

    # Create project
    project_ref = db.collection("projects").document()

    project_ref.set({
        "title": extraction.get("project_title"),
        "summary": extraction.get("summary", ""),
        "deadline": extraction.get("project_deadline"),
        "status": "active",
    })

    project_id = project_ref.id

    # Create tasks
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



    return f"Saved project {project_id} with {len(extraction.get('tasks', []))} tasks."