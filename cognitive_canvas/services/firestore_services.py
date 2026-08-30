from google.cloud import firestore
from .event_services import create_event


db = firestore.Client(project="negnq-agenticassistant")

def claim_event(event_id: str) -> bool:
    """
    Atomically claim an event for processing.

    Returns True if this dispatcher successfully claimed it.
    Returns False if another dispatcher already claimed/completed it.
    """

    event_ref = db.collection("events").document(event_id)
    transaction = db.transaction()

    @firestore.transactional
    def _claim(transaction):
        snapshot = event_ref.get(transaction=transaction)

        if not snapshot.exists:
            return False

        event = snapshot.to_dict()
        status = event.get("status")

        # Only PENDING events can be claimed.
        if status != "PENDING":
            return False

        transaction.update(event_ref, {
            "status": "PROCESSING",
            "processing_started_at": firestore.SERVER_TIMESTAMP,
        })

        return True

    return _claim(transaction)

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
    depends_on: list[str] | None = None,
    estimated_minutes: int | None = None,
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

    existing_task = next(existing, None)

    if existing_task:
        return existing_task.id

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
        "depends_on": depends_on or [],
        "estimated_minutes": estimated_minutes,
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

def get_task_readiness(task_id: str) -> dict:
    task = get_task(task_id)

    if not task:
        return {
            "task_id": task_id,
            "ready": False,
            "reason": "Task not found",
        }

    dependencies = task.get("depends_on", [])

    if not dependencies:
        return {
            "task_id": task_id,
            "ready": True,
            "reason": "No dependencies",
        }

    dependency_tasks = []

    for dependency_id in dependencies:
        dependency = get_task(dependency_id)

        if not dependency:
            return {
                "task_id": task_id,
                "ready": False,
                "reason": f"Dependency {dependency_id} not found",
            }

        dependency_tasks.append(dependency)

    incomplete = [
        dependency
        for dependency in dependency_tasks
        if dependency.get("status") != "completed"
    ]

    if incomplete:
        return {
            "task_id": task_id,
            "ready": False,
            "reason": "Waiting for dependencies",
            "blocked_by": [
                dependency["id"]
                for dependency in incomplete
            ],
        }

    return {
        "task_id": task_id,
        "ready": True,
        "reason": "All dependencies completed",
    }

def get_ready_tasks(project_id: str) -> list[dict]:
    """
    Return queued tasks whose dependencies are all completed.
    """

    docs = (
        db.collection("tasks")
        .where("project_id", "==", project_id)
        .where("status", "==", "queued")
        .stream()
    )

    ready_tasks = []

    for doc in docs:
        task = {
            "id": doc.id,
            **doc.to_dict(),
        }

        readiness = get_task_readiness(task["id"])

        if readiness["ready"]:
            ready_tasks.append(task)

    return ready_tasks

def complete_task(task_id: str) -> str:
    task_ref = db.collection("tasks").document(task_id)

    task = task_ref.get()

    if not task.exists:
        return f"Task {task_id} not found."

    task_ref.update({
        "status": "completed",
        "completed_at": firestore.SERVER_TIMESTAMP,
    })

    return f"Task {task_id} completed successfully."

def start_task(task_id: str) -> str:
    task_ref = db.collection("tasks").document(task_id)

    task = task_ref.get()

    if not task.exists:
        return f"Task {task_id} not found."

    task_ref.update({
        "status": "in-progress",
        "started_at": firestore.SERVER_TIMESTAMP,
    })

    return f"Task {task_id} started successfully."

def get_next_task(project_id: str) -> dict | None:
    ready_tasks = get_ready_tasks(project_id)

    if not ready_tasks:
        return None

    def sort_key(task):
        priority_order = {
            "high": 0,
            "medium": 1,
            "low": 2,
        }

        priority = priority_order.get(
            task.get("priority", "medium"),
            1,
        )

        due_date = task.get("due_date")

        # Tasks with due dates come before tasks without one
        if due_date:
            return (priority, 0, due_date)

        return (priority, 1, "")

    ready_tasks.sort(key=sort_key)

    return ready_tasks[0]

def schedule_tasks(project_id: str, available_minutes: int) -> list[dict]:
    """
    Build a simple schedule from currently ready tasks.

    Tasks are selected by priority and due date, while respecting
    the available time budget.
    """

    if available_minutes <= 0:
        return []

    ready_tasks = get_ready_tasks(project_id)

    def sort_key(task):
        priority_order = {
            "high": 0,
            "medium": 1,
            "low": 2,
        }

        priority = priority_order.get(
            task.get("priority", "medium"),
            1,
        )

        due_date = task.get("due_date")

        if due_date:
            return (priority, 0, due_date)

        return (priority, 1, "")

    ready_tasks.sort(key=sort_key)

    schedule = []
    remaining_minutes = available_minutes

    for task in ready_tasks:
        estimated = task.get("estimated_minutes")

        # We cannot fit a task if we don't know its duration.
        if not estimated:
            continue

        if estimated <= remaining_minutes:
            schedule.append({
                "task_id": task["id"],
                "title": task["title"],
                "estimated_minutes": estimated,
                "priority": task.get("priority", "medium"),
                "due_date": task.get("due_date"),
            })

            remaining_minutes -= estimated

    return schedule

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

def recover_stale_event(event_id: str) -> bool:
    """
    Move a stale PROCESSING event back to PENDING.

    Returns True if recovery was performed.
    """

    event_ref = db.collection("events").document(event_id)
    transaction = db.transaction()

    @firestore.transactional
    def _recover(transaction):
        snapshot = event_ref.get(transaction=transaction)

        if not snapshot.exists:
            return False

        event = snapshot.to_dict()

        if event.get("status") != "PROCESSING":
            return False

        transaction.update(event_ref, {
            "status": "PENDING",
            "processing_started_at": firestore.DELETE_FIELD,
            "recovery_count": firestore.Increment(1),
        })

        return True

    return _recover(transaction)

def has_tasks_for_event(source_event_id: str) -> bool:
    docs = (
        db.collection("tasks")
        .where("source_event_id", "==", source_event_id)
        .limit(1)
        .stream()
    )

    return next(docs, None) is not None