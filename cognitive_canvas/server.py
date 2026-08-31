import os
import sys
import json
import asyncio
from pathlib import Path
from typing import Optional, Any, Dict
import uvicorn
from fastapi import FastAPI, HTTPException, APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# Add project root to sys.path
current_file = Path(__file__).resolve()
cognitive_canvas_dir = current_file.parent
project_root = cognitive_canvas_dir.parent

if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
if str(cognitive_canvas_dir) not in sys.path:
    sys.path.insert(0, str(cognitive_canvas_dir))

from google.adk.cli.fast_api import get_fast_api_app
from google.adk.runners import InMemoryRunner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from cognitive_canvas.services.firestore_services import db, create_task as db_create_task, update_task as db_update_task
from cognitive_canvas.agent import MODEL_CASCADE, get_agent

agents_dir = str(cognitive_canvas_dir)

# Initialize the ADK FastAPI server with all origins allowed
app: FastAPI = get_fast_api_app(
    agents_dir=agents_dir,
    allow_origins=["*"],
    web=False,
)

# Persistent Session Service for Multi-Turn Conversations
session_service = InMemorySessionService()
user_sessions: Dict[str, str] = {}


def is_quota_error(error: Exception) -> bool:
    """Detect 429, Resource Exhausted, and Quota errors."""
    error_text = str(error).upper()
    return (
        "429" in error_text
        or "RESOURCE_EXHAUSTED" in error_text
        or "QUOTA" in error_text
        or "RATE LIMIT" in error_text
        or "RATE_LIMIT" in error_text
    )


# ─── API Router (Mounted at both / and /api) ────────────────────

api_router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    user_id: Optional[str] = "web_user"
    session_id: Optional[str] = None


@api_router.get("/model-info")
async def get_model_info():
    """Returns the primary model and fallback cascade order."""
    return {
        "primary_model": MODEL_CASCADE[0],
        "fallback_cascade": MODEL_CASCADE,
    }


@api_router.post("/chat")
async def chat_with_fallback(req: ChatRequest):
    """
    Executes the unified agent with automatic fallback on quota exhaustion.
    Streams SSE events for real-time tokens, fallback notices, and final output.
    Maintains persistent multi-turn conversational memory per user.
    """
    user_id = req.user_id or "web_user"

    # Maintain or initialize persistent session
    session_id = req.session_id or user_sessions.get(user_id)
    if not session_id:
        new_sess = await session_service.create_session(
            app_name="cognitive_canvas",
            user_id=user_id,
        )
        session_id = new_sess.id
        user_sessions[user_id] = session_id

    async def event_generator():
        last_error = None
        
        for idx, model_name in enumerate(MODEL_CASCADE):
            try:
                # If this is a fallback attempt, emit a fallback warning event first
                if idx > 0:
                    prev_model = MODEL_CASCADE[idx - 1]
                    fallback_warning = {
                        "type": "fallback_warning",
                        "failed_model": prev_model,
                        "fallback_model": model_name,
                        "message": f"⚠️ {prev_model} quota limit reached. Automatically falling back to {model_name}...",
                    }
                    yield f"data: {json.dumps(fallback_warning)}\n\n"
                    print(f"⚠️ [Fallback] Switching from {prev_model} to {model_name} due to quota exhaustion.")
                
                # Instantiate agent with this model and shared session service
                agent = get_agent(model_name)
                runner = InMemoryRunner(
                    agent=agent,
                    app_name="cognitive_canvas",
                )
                runner.session_service = session_service
                
                # Stream the agent response
                async for response in runner.run_async(
                    user_id=user_id,
                    session_id=session_id,
                    new_message=types.Content(
                        role="user",
                        parts=[types.Part(text=req.message)],
                    ),
                ):
                    if response.content and response.content.parts:
                        for part in response.content.parts:
                            if part.text:
                                chunk = {
                                    "type": "text",
                                    "text": part.text,
                                    "model": model_name,
                                    "is_fallback": idx > 0,
                                    "session_id": session_id,
                                }
                                yield f"data: {json.dumps(chunk)}\n\n"
                
                # Successfully completed
                done_event = {
                    "type": "done",
                    "model": model_name,
                    "is_fallback": idx > 0,
                    "session_id": session_id,
                }
                yield f"data: {json.dumps(done_event)}\n\n"
                return

            except Exception as e:
                last_error = e
                print(f"❌ Error with model {model_name}: {e}")
                
                if is_quota_error(e):
                    # Quota error: continue to next fallback model
                    continue
                else:
                    # Other error: notify client and exit
                    error_event = {
                        "type": "error",
                        "message": str(e),
                        "model": model_name,
                    }
                    yield f"data: {json.dumps(error_event)}\n\n"
                    return
        
        # If all models in the cascade failed
        final_error = {
            "type": "error",
            "message": f"All models in fallback cascade exhausted quota. Last error: {last_error}",
        }
        yield f"data: {json.dumps(final_error)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@api_router.get("/projects")
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


@api_router.get("/projects/{project_id}")
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


@api_router.get("/schedule")
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
                "title": t.get("title") or "Untitled Task",
                "project": p_title,
                "projectId": t.get("project_id"),
                "priority": t.get("priority") or "medium",
                "status": t.get("status") or "queued",
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
    due_date: Optional[str] = None
    title: Optional[str] = None
    priority: Optional[str] = None


class CreateTaskRequest(BaseModel):
    title: str
    project_id: Optional[str] = None
    due_date: Optional[str] = None
    priority: Optional[str] = "medium"
    task_type: Optional[str] = "task"
    details: Optional[str] = ""
    estimated_minutes: Optional[int] = None


@api_router.post("/tasks")
async def create_task_endpoint(body: CreateTaskRequest):
    """Create and optionally schedule a task in Firestore."""
    try:
        res = db_create_task(
            title=body.title,
            due_date=body.due_date,
            priority=body.priority or "medium",
            task_type=body.task_type or "task",
            details=body.details or "",
            project_id=body.project_id or "unassigned",
            estimated_minutes=body.estimated_minutes,
        )
        return {"status": "success", "task_id": res["task_id"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@api_router.patch("/tasks/{task_id}")
async def update_task_status(task_id: str, body: TaskUpdate):
    """Toggle or update a task status in Firestore."""
    try:
        updates = {}
        if body.done is not None:
            updates["status"] = "completed" if body.done else "queued"
        elif body.status:
            updates["status"] = body.status
        if body.due_date:
            updates["due_date"] = body.due_date
        if body.title:
            updates["title"] = body.title
        if body.priority:
            updates["priority"] = body.priority
            
        if updates:
            db_update_task(task_id, updates)
            
        return {"status": "success", "task_id": task_id, "updates": updates}
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Mount router for both unprefixed (e.g. /chat) and /api (e.g. /api/chat)
app.include_router(api_router)
app.include_router(api_router, prefix="/api")


if __name__ == "__main__":
    print("🚀 Starting Cognitive Canvas Unified Server on http://127.0.0.1:8000")
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)
