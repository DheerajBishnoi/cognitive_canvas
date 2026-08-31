from .task_tools import create_task, update_task, delete_task, list_tasks
from .project_tools import create_project, plan_project_tasks, list_projects
from .research_tools import search_web, save_research_findings

ALL_AGENT_TOOLS = [
    create_task,
    update_task,
    delete_task,
    list_tasks,
    create_project,
    plan_project_tasks,
    list_projects,
    search_web,
    save_research_findings,
]

__all__ = [
    "create_task",
    "update_task",
    "delete_task",
    "list_tasks",
    "create_project",
    "plan_project_tasks",
    "list_projects",
    "search_web",
    "save_research_findings",
    "ALL_AGENT_TOOLS",
]
