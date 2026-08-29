import asyncio
from pathlib import Path

from dotenv import load_dotenv

env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(env_path)

from google.adk.runners import InMemoryRunner
from google.genai import types

from .firestore_services import db
from ..agents.router_agent import router_agent


APP_NAME = "cognitive_canvas_router"
USER_ID = "event_dispatcher"


def get_pending_events(limit: int = 10) -> list[dict]:
    docs = (
        db.collection("events")
        .where("processed", "==", False)
        .limit(limit)
        .stream()
    )

    return [
        {
            "id": doc.id,
            **doc.to_dict(),
        }
        for doc in docs
    ]


def mark_event_processed(event_id: str):
    db.collection("events").document(event_id).update({
        "processed": True
    })


async def process_event(event: dict):
    runner = InMemoryRunner(
        agent=router_agent,
        app_name=APP_NAME,
    )

    session = await runner.session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
    )

    prompt = f"""
A new Cognitive Canvas event has arrived.

Event:
{event}

Process this event.

Route the task to the appropriate specialist agent.
Do not invent information that is not present in the event.
"""

    print(f"\nProcessing event: {event['id']}")

    async for response in runner.run_async(
        user_id=USER_ID,
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

    mark_event_processed(event["id"])
    print(f"Event processed: {event['id']}")


async def process_pending_events():
    events = get_pending_events()

    print(f"Found {len(events)} pending events.")

    for event in events:
        try:
            await process_event(event)
        except Exception as e:
            print(f"Failed to process {event['id']}: {e}")


async def run_dispatcher():
    print("🚀 Event dispatcher started. Watching Firestore...")

    while True:
        try:
            await process_pending_events()
        except Exception as e:
            print(f"Dispatcher error: {e}")

        await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(run_dispatcher())