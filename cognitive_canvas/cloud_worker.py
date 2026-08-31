import asyncio
import logging
import uuid
from flask import Flask, request
from google.events.cloud import firestore

from .services.event_dispatcher import process_event

app = Flask(__name__)

logger = logging.getLogger(__name__)

invocation_id = str(uuid.uuid4())

logger.info(
    "EVENT INVOCATION START: invocation=%s",
    invocation_id,
)

@app.post("/")
def handle_event():
    try:
        # Eventarc sends Firestore events as protobuf.
        content_type = request.headers.get("Content-Type", "")
        logger.info("Content-Type: %s", content_type)

        event_data = firestore.DocumentEventData()
        event_data._pb.ParseFromString(request.data)

        document = event_data.value

        logger.info("Received Firestore event: %s", document.name)

        # Convert Firestore protobuf fields into our normal event format
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

        return "Processed", 200

    except Exception:
        logger.exception("Failed to process Firestore event")
        return "Processing failed", 500


def decode_firestore_value(value):
    """Convert a Firestore protobuf Value into a normal Python value."""

    # Proto Plus exposes the underlying protobuf message through `_pb`.
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

