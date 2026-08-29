from google.adk.agents import LlmAgent

from .research_agent import research_agent
from .planner_agent import planner_agent


router_agent = LlmAgent(
    name="router_agent",
    model="gemini-3.1-flash-lite",

    description="Routes tasks to the appropriate specialist agent.",

    instruction="""
You are the Cognitive Canvas Router.

Route each request to the appropriate specialist.

IMPORTANT: Workspace operations take priority over research.

- If the user asks to read, inspect, retrieve, update, modify,
  complete, prioritize, or manage an existing task/project
  → transfer to planner_agent.

- If the task requires external investigation, comparison,
  fact-finding, discovering information, or web research
  → transfer to research_agent.

- If the request involves scheduling, prioritization, deadlines,
  dependencies, breaking goals into steps, or organizing work
  → transfer to planner_agent.

- Otherwise → transfer to planner_agent.

Do NOT perform the task yourself.
Always transfer the request to the appropriate specialist.
""",
    sub_agents=[
        research_agent,
        planner_agent,
    ],
)