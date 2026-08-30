from google.adk.agents import LlmAgent
from pydantic import BaseModel
from typing import Optional
import json

from google.adk.agents import LlmAgent
from pydantic import BaseModel
from typing import Optional

from .services.firestore_services import save_extraction
from .agents.router_agent import router_agent

class Task(BaseModel):
    title: str
    task_type: str
    priority: str
    due_date: Optional[str] = None
    details: str = ""


class ExtractionResult(BaseModel):
    summary: str
    project_title: Optional[str] = None
    project_deadline: Optional[str] = None

    intent: str

    tasks: list[Task]

def save_to_firestore(callback_context):
    result = callback_context.state.get("extraction_result")

    if not result:
        return

    if isinstance(result, str):
        result = json.loads(result)

    save_extraction(result)


root_agent = LlmAgent(
    name="root_agent",
    model="gemini-3.1-flash-lite",

    description="Extracts structured work from messy user input.",

    instruction="""
You are the Cognitive Canvas Extraction Agent.

Your responsibility is ONLY to understand the user's request and
convert it into a structured representation.

You do NOT plan.
You do NOT decompose goals.
You do NOT perform research.
You do NOT create research steps.
You do NOT create planning steps.
You do NOT decide which specialist agent should handle the request.

Determine the user's primary intent:

- "task": The user wants a specific piece of work captured as a task.
- "plan": The user wants goals organized, prioritized, scheduled,
  decomposed, or turned into an actionable plan.
- "research": The user wants information investigated, compared,
  verified, or researched.

IMPORTANT TASK EXTRACTION RULE:

Only populate "tasks" when intent is "task".

If intent is "plan":
- tasks MUST be an empty list.
- Put the user's overall planning goal in summary.
- Preserve relevant project information.

If intent is "research":
- tasks MUST be an empty list.
- Put the research request in summary.
- Preserve relevant project information.

For "task":
- Extract the specific task(s) explicitly requested by the user.

Extract only information supported by the user's input.
Never invent deadlines.

If there is no project, project_title should be null.
If there is no project deadline, project_deadline should be null.

Give extracted tasks a task_type such as study, research, work,
personal, etc.

Priority must be high, medium, or low.

Keep task titles concise.
Put useful context in details.
""",

    output_schema=ExtractionResult,

    output_key="extraction_result",

    after_agent_callback=save_to_firestore,
)