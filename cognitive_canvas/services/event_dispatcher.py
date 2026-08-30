import asyncio
from pathlib import Path
from google.cloud import firestore
from dotenv import load_dotenv
from datetime import datetime, timezone, timedelta

env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(env_path)

from google.adk.runners import InMemoryRunner
from google.genai import types

from .firestore_services import claim_event, db, recover_stale_event, save_research_result
from ..agents.router_agent import router_agent
from ..agents.research_agent import research_fallback_agent


APP_NAME = "cognitive_canvas_router"
USER_ID = "event_dispatcher"

# Initial delay after a Gemini 429
INITIAL_BACKOFF = 5

# Maximum delay between retries
MAX_BACKOFF = 60


def get_pending_events(limit: int = 10) -> list[dict]:
    events = []

    docs = db.collection("events").stream()

    now = datetime.now(timezone.utc)
    timeout = timedelta(minutes=5)

    for doc in docs:
        event = {
            "id": doc.id,
            **doc.to_dict(),
        }

        status = event.get("status")

        if status == "PENDING":
            events.append(event)

        elif status == "PROCESSING":
            started_at = event.get("processing_started_at")

            if started_at:
                # Firestore Timestamp → Python datetime
                if started_at.tzinfo is None:
                    started_at = started_at.replace(tzinfo=timezone.utc)

                if now - started_at > timeout:
                    print(
                        f"⚠️ Recovering stale event: {doc.id}"
                    )

                    if recover_stale_event(doc.id):
                        event["status"] = "PENDING"
                        events.append(event)

        if len(events) >= limit:
            break

    return events

def mark_event_completed(event_id: str):
    db.collection("events").document(event_id).update({
        "status": "COMPLETED",
        "processed": True,
        "processing_started_at": firestore.DELETE_FIELD,
    })

def mark_event_processing(event_id: str):
    db.collection("events").document(event_id).update({
        "status": "PROCESSING",
        "processing_started_at": firestore.SERVER_TIMESTAMP,
    })


def mark_event_failed(event_id: str, error: Exception):
    event_ref = db.collection("events").document(event_id)
    event = event_ref.get()

    attempt_count = event.to_dict().get("attempt_count", 0) + 1
    max_attempts = event.to_dict().get("max_attempts", 3)

    if attempt_count >= max_attempts:
        status = "DEAD"
        processed = False
        print(
            f"☠️ Event {event_id} reached maximum attempts "
            f"({max_attempts}). Marking as DEAD."
        )
    else:
        status = "FAILED"
        processed = False

    event_ref.update({
        "status": status,
        "processed": processed,
        "error": str(error),
        "attempt_count": attempt_count,
        "processing_started_at": firestore.DELETE_FIELD,
    })

def is_rate_limit_error(error: Exception) -> bool:
    """
    Detect Gemini/API quota errors.
    """
    error_text = str(error).upper()

    return (
        "429" in error_text
        or "RESOURCE_EXHAUSTED" in error_text
        or "QUOTA" in error_text
        or "RATE LIMIT" in error_text
    )

def is_event_processed(event_id: str) -> bool:
    doc = db.collection("events").document(event_id).get()

    if not doc.exists:
        return False

    return doc.to_dict().get("processed", False)

async def process_event(event: dict):

    if is_event_processed(event["id"]):
        print(f"⏭️ Event already processed: {event['id']}")
        return

    if not claim_event(event["id"]):
        print(f"⏭️ Event already claimed or processed: {event['id']}")
        return


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
    # mark_event_processing(event["id"])
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
    
    # raise Exception("TEST FAILURE")
    mark_event_completed(event["id"])

    print(f"\nEvent processed: {event['id']}")
    

    # print(f"\nProcessing event: {event['id']}")

async def process_research_fallback(event: dict):
    runner = InMemoryRunner(
        agent=research_fallback_agent,
        app_name=APP_NAME,
    )

    session = await runner.session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
    )

    prompt = f"""
A research request could not be completed because the
primary research agent encountered a Gemini quota/rate-limit error.

Event:
{event}

Provide the best useful analysis possible using your existing knowledge.
Do not claim to have performed web research.
Clearly state when current external verification is unavailable.
"""

    print(f"\n⚠️ Running research fallback for event: {event['id']}")

    output_parts = []

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
                    output_parts.append(part.text)

    findings = "\n".join(output_parts)

    payload = event.get("payload", {})

    save_research_result(
        event_id=event["id"],
        project_id=payload.get("project_id"),
        query=payload.get("query", ""),
        summary=findings,
        source_type="fallback",
    )

    mark_event_completed(event["id"])

    print(f"\nFallback completed: {event['id']}")

async def process_pending_events():
    events = get_pending_events()

    print(f"Found {len(events)} pending events.")

    for event in events:
        try:
            await process_event(event)

        except Exception as e:
            print(f"Failed to process {event['id']}: {e}")

            if not is_rate_limit_error(e):
                mark_event_failed(event["id"], e)

            if is_rate_limit_error(e):
                if event.get("type") == "RESEARCH_REQUESTED":
                    try:
                        await process_research_fallback(event)
                        continue

                    except Exception as fallback_error:
                        print(
                            f"Research fallback also failed: {fallback_error}"
                        )

                        mark_event_failed(event["id"], fallback_error)

                        raise RuntimeError("GEMINI_RATE_LIMIT") from fallback_error

                print(
                    "⚠️ Gemini quota/rate limit detected. "
                    "Stopping this processing batch."
                )

                raise RuntimeError("GEMINI_RATE_LIMIT") from e


async def run_dispatcher():
    print("🚀 Event dispatcher started. Watching Firestore...")

    backoff = INITIAL_BACKOFF

    while True:
        try:
            await process_pending_events()

            # Successful batch: reset backoff
            backoff = INITIAL_BACKOFF

        except RuntimeError as e:
            if str(e) == "GEMINI_RATE_LIMIT":
                print(
                    f"⏳ Waiting {backoff} seconds before retrying..."
                )

                await asyncio.sleep(backoff)

                # Exponential backoff
                backoff = min(backoff * 2, MAX_BACKOFF)

            else:
                print(f"Dispatcher error: {e}")

        except Exception as e:
            print(f"Dispatcher error: {e}")

            # Normal unexpected error
            await asyncio.sleep(5)

        else:
            # Normal polling interval
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(run_dispatcher())