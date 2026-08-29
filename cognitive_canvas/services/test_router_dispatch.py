import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

env_path = Path(__file__).resolve().parents[1] / ".env"

print("Looking for .env at:", env_path)
print(".env exists:", env_path.exists())

load_dotenv(env_path)

print("API key loaded:", bool(os.getenv("GEMINI_API_KEY")))

from google.adk.runners import InMemoryRunner
from google.genai import types

from cognitive_canvas.agents.router_agent import router_agent

async def main():
    runner = InMemoryRunner(
        agent=router_agent,
        app_name="cognitive_canvas_router_test",
    )

    session = await runner.session_service.create_session(
        app_name="cognitive_canvas_router_test",
        user_id="event_dispatcher",
    )

    event = {
        "type": "TASK_CREATED",
        "entity_id": "TEST123",
        "payload": {
            "project_id": "TEST_PROJECT",
            "task_title": "Shortlist a laptop for college",
            "task_type": "research",
        },
    }

    prompt = f"""
A new Cognitive Canvas event has arrived.

Event:
{event}

Process this event and route the task to the appropriate specialist.
"""

    async for response in runner.run_async(
        user_id="event_dispatcher",
        session_id=session.id,
        new_message=types.Content(
            role="user",
            parts=[types.Part(text=prompt)],
        ),
    ):
        if response.content and response.content.parts:
            for part in response.content.parts:
                if part.text:
                    print(part.text)


if __name__ == "__main__":
    asyncio.run(main())