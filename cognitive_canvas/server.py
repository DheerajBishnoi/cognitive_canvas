import os
import sys
from pathlib import Path
from typing import Optional, Any
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Add project root to sys.path
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from google.adk.cli.fast_api import get_fast_api_app
from cognitive_canvas.services.firestore_services import db

agents_dir = str(Path(__file__).resolve().parent)

# Initialize the ADK FastAPI server with all origins allowed
app: FastAPI = get_fast_api_app(
    agents_dir=agents_dir,
    allow_origins=["*"],
    web=False,
)

# ─── Firestore Custom REST API Endpoints ─────────────────────────

@app.get("/api/projects")
async def get_projects():
    """Fetch all projects from Firestore with task completion stats."""
    try:
        projects_docs = db.collection("projects").stream()
        tasks_docs = db.collection("tasks").stream()
        
        # Group tasks by project_id
        tasks_by_project = {}
        for doc in tasks_docs:
            t = {**doc.to_dict(), "id": doc.id}
            p_id = t.get("project_id")
            if p_id:
                tasks_by_project.setdefault(p_id, []).append(t)
        
        projects = []
        for doc in projects_docs:
            p = {**doc.to_dict(), "id": doc.id}
            p_tasks = tasks_by_project.get(doc.id, [])
            done_count = sum(1 for t in p_tasks if t.get("status") in ["completed", "done"])
            
            projects.append({
                "id": p["id"],
                "title": p.get("title") or "Untitled Project",
                "summary": p.get("summary") or "",
                "deadline": p.get("deadline"),
                "status": p.get("status") or "active",
                "taskCount": len(p_tasks),
                "completedCount": done_count,
            })
            
        return {"projects": projects}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/projects/{project_id}")
async def get_project_detail(project_id: str):
    """Fetch a single project with its notes and tasks."""
    try:
        p_doc = db.collection("projects").document(project_id).get()
        if not p_doc.exists:
            raise HTTPException(status_code=404, detail="Project not found")
        
        project = {**p_doc.to_dict(), "id": p_doc.id}
        
        # Get tasks for this project
        tasks_query = db.collection("tasks").where("project_id", "==", project_id).stream()
        tasks = []
        for doc in tasks_query:
            t = {**doc.to_dict(), "id": doc.id}
            tasks.append({
                "id": t["id"],
                "title": t.get("title") or "Untitled Task",
                "taskType": t.get("task_type") or "task",
                "priority": t.get("priority") or "medium",
                "details": t.get("details") or "",
                "status": t.get("status") or "queued",
                "done": t.get("status") in ["completed", "done"],
                "dueDate": t.get("due_date"),
                "estimatedMinutes": t.get("estimated_minutes"),
            })
            
        # Get notes or research results linked to this project
        research_docs = db.collection("research_results").where("project_id", "==", project_id).stream()
        notes = []
        for r_doc in research_docs:
            r = r_doc.to_dict()
            if r.get("summary"):
                notes.append(f"Research on '{r.get('query', '')}': {r.get('summary')}")
        
        return {
            "id": project["id"],
            "title": project.get("title") or "Untitled Project",
            "summary": project.get("summary") or "",
            "deadline": project.get("deadline"),
            "status": project.get("status") or "active",
            "notes": notes,
            "tasks": tasks,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/schedule")
async def get_schedule():
    """Fetch all tasks and build the daily schedule."""
    try:
        tasks_docs = db.collection("tasks").stream()
        projects_docs = db.collection("projects").stream()
        
        projects_map = {doc.id: doc.to_dict().get("title", "") for doc in projects_docs}
        
        tasks_list = []
        for doc in tasks_docs:
            t = {**doc.to_dict(), "id": doc.id}
            p_title = projects_map.get(t.get("project_id"), "")
            tasks_list.append({
                "id": t["id"],
                "text": t.get("title") or "Untitled Task",
                "project": p_title,
                "priority": t.get("priority") or "medium",
                "done": t.get("status") in ["completed", "done"],
                "dueDate": t.get("due_date"),
                "estimatedMinutes": t.get("estimated_minutes"),
                "taskType": t.get("task_type") or "task",
            })
            
        return {"schedule": tasks_list}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class TaskUpdate(BaseModel):
    done: Optional[bool] = None
    status: Optional[str] = None


@app.patch("/api/tasks/{task_id}")
async def update_task_status(task_id: str, body: TaskUpdate):
    """Toggle or update a task status in Firestore."""
    try:
        task_ref = db.collection("tasks").document(task_id)
        task_doc = task_ref.get()
        if not task_doc.exists:
            raise HTTPException(status_code=404, detail="Task not found")
        
        updates = {}
        if body.done is not None:
            updates["status"] = "completed" if body.done else "queued"
        elif body.status:
            updates["status"] = body.status
            
        if updates:
            task_ref.update(updates)
            
        return {"status": "success", "task_id": task_id, "updates": updates}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    print("🚀 Starting Cognitive Canvas Unified Server on http://127.0.0.1:8000")
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)
