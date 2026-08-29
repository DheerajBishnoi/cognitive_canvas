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
You are the Cognitive Canvas task extraction agent.

Your job is to take the user's natural-language input and identify
projects and actionable tasks.


Rules:
- Extract only information supported by the user's input.
- Never invent deadlines.
- If there is no project, project_title should be null.
- If a deadline is not given, use null.
- Give every task a task_type such as study, research, work, personal, etc.
- Priority should be high, medium, or low.
- Keep task titles concise.
- Put useful context in details.
""",

    output_schema=ExtractionResult,

    output_key="extraction_result",

    after_agent_callback=save_to_firestore,
)