import logging

from google.cloud import firestore
from google.adk.runners import InMemoryRunner
from google.genai import types

from .firestore_services import (
    claim_event,
    db,
    save_research_result,
)
from ..agents.router_agent import router_agent
from ..agents.research_agent import research_fallback_agent


logger = logging.getLogger(__name__)

APP_NAME = "cognitive_canvas_router"
USER_ID = "event_dispatcher"


def mark_event_completed(event_id: str):
    db.collection("events").document(event_id).update({
        "status": "COMPLETED",
        "processed": True,
        "processing_started_at": firestore.DELETE_FIELD,
    })


def mark_event_failed(event_id: str, error: Exception):
    event_ref = db.collection("events").document(event_id)
    snapshot = event_ref.get()

    if not snapshot.exists:
        logger.error("Cannot mark missing event as failed: %s", event_id)
        return

    event = snapshot.to_dict()

    attempt_count = event.get("attempt_count", 0) + 1
    max_attempts = event.get("max_attempts", 3)

    if attempt_count >= max_attempts:
        status = "DEAD"
        logger.error(
            "☠️ Event %s reached maximum attempts (%s). "
            "Marking as DEAD.",
            event_id,
            max_attempts,
        )
    else:
        # IMPORTANT:
        # Return it to PENDING so Eventarc's retry can claim it again.
        status = "PENDING"

    event_ref.update({
        "status": status,
        "processed": False,
        "error": str(error),
        "attempt_count": attempt_count,
        "processing_started_at": firestore.DELETE_FIELD,
    })


def is_rate_limit_error(error: Exception) -> bool:
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

    event_id = event["id"]

    if is_event_processed(event_id):
        logger.info("⏭️ Event already processed: %s", event_id)
        return

    if not claim_event(event_id):
        logger.info("⏭️ Event was not claimed: %s", event_id)
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

    logger.info("Processing event: %s", event_id)

    try:
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
                        logger.info(part.text)

        mark_event_completed(event_id)

        logger.info("Event processed: %s", event_id)

    except Exception as e:
        logger.exception("Event processing failed: %s", event_id)

        mark_event_failed(event_id, e)

        raise


async def process_research_fallback(event: dict):

    event_id = event["id"]

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

    logger.info("⚠️ Running research fallback for event: %s", event_id)

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
                    logger.info(part.text)
                    output_parts.append(part.text)

    findings = "\n".join(output_parts)

    payload = event.get("payload", {})

    save_research_result(
        event_id=event_id,
        project_id=payload.get("project_id"),
        query=payload.get("query", ""),
        summary=findings,
        source_type="fallback",
    )

    mark_event_completed(event_id)

    logger.info("Fallback completed: %s", event_id)