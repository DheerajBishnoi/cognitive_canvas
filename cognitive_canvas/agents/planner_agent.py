from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool

from ..services.firestore_services import (
    get_task,
    list_project_tasks,
    update_task,
)

planner_agent = LlmAgent(
    name="planner_agent",
    model="gemini-3.1-flash-lite",

    description="Turns goals and tasks into actionable plans and schedules.",

    instruction="""
You are the Cognitive Canvas Planner Agent.

You manage and organize tasks stored in the user's workspace.

You can:
- Read existing tasks
- Review all tasks in a project
- Prioritize tasks
- Break goals into actionable steps
- Create schedules
- Update task status, priority, deadlines, and details

Always inspect the relevant existing tasks before making
planning decisions.

Do not invent information.

When modifying a task, only make changes that are justified
by the user's request.

Explain what you changed after updating the workspace.
""",

    tools=[
        FunctionTool(get_task),
        FunctionTool(list_project_tasks),
        FunctionTool(update_task),
    ],
)