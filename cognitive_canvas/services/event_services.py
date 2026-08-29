from datetime import datetime, timezone
import uuid


def create_event(event_type: str, entity_id: str, payload: dict) -> dict:
    return {
        "event_id": str(uuid.uuid4()),
        "type": event_type,
        "entity_id": entity_id,
        "payload": payload,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }