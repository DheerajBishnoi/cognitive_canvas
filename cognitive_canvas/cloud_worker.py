import asyncio
import logging
import uuid

from flask import Flask, request
from google.events.cloud import firestore

from .services.event_dispatcher import process_event

from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(env_path)

app = Flask(__name__)

logger = logging.getLogger(__name__)


@app.post("/")
def handle_event():
    invocation_id = str(uuid.uuid4())

    logger.info(
        "EVENT INVOCATION START: invocation=%s",
        invocation_id,
    )

    try:
        content_type = request.headers.get("Content-Type", "")
        logger.info("Content-Type: %s", content_type)

        # Eventarc sends Firestore events as protobuf.
        event_data = firestore.DocumentEventData()
        event_data._pb.ParseFromString(request.data)

        document = event_data.value

        logger.info(
            "Received Firestore event: %s",
            document.name,
        )

        event = {
            "id": document.name.split("/")[-1],
        }

        for key, value in document.fields.items():
            event[key] = decode_firestore_value(value)

        logger.info("Decoded event: %s", event)

        logger.info(
            "DISPATCHING: invocation=%s event=%s",
            invocation_id,
            event["id"],
        )

        asyncio.run(process_event(event))

        logger.info(
            "EVENT INVOCATION SUCCESS: invocation=%s event=%s",
            invocation_id,
            event["id"],
        )

        return "Processed", 200

    except Exception:
        logger.exception(
            "EVENT INVOCATION FAILED: invocation=%s",
            invocation_id,
        )

        # Non-2xx tells Eventarc the delivery failed,
        # allowing its retry mechanism to handle it.
        return "Processing failed", 500


def decode_firestore_value(value):
    """Convert Firestore protobuf Value into a normal Python value."""

    kind = value._pb.WhichOneof("value_type")

    if kind == "string_value":
        return value.string_value

    if kind == "boolean_value":
        return value.boolean_value

    if kind == "integer_value":
        return value.integer_value

    if kind == "double_value":
        return value.double_value

    if kind == "timestamp_value":
        return value.timestamp_value

    if kind == "null_value":
        return None

    if kind == "map_value":
        return {
            key: decode_firestore_value(field_value)
            for key, field_value in value.map_value.fields.items()
        }

    if kind == "array_value":
        return [
            decode_firestore_value(item)
            for item in value.array_value.values
        ]

    if kind == "bytes_value":
        return value.bytes_value

    if kind == "reference_value":
        return value.reference_value

    if kind == "geo_point_value":
        return {
            "latitude": value.geo_point_value.latitude,
            "longitude": value.geo_point_value.longitude,
        }

    return None


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8081, debug=False, use_reloader=False)