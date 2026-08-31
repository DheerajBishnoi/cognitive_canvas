import requests
from google.events.cloud import firestore

from cognitive_canvas.services.firestore_services import db


EVENT_ID = "local-test-001"

# 1. Create the real event in Firestore
db.collection("events").document(EVENT_ID).set({
    "type": "TASK_CREATED",
    "entity_id": "local-test",
    "status": "PENDING",
    "processed": False,
    "event_id": EVENT_ID,
    "attempt_count": 0,
    "max_attempts": 3,
    "payload": {
        "project_id": "cloud-test-project",
        "task_title": "Local event-driven test",
        "task_type": "test",
    },
})

print("Created Firestore event:", EVENT_ID)


# 2. Create an Eventarc-style protobuf
event = firestore.DocumentEventData()

event.value.name = (
    "projects/negnq-agenticassistant/"
    "databases/(default)/documents/events/local-test-001"
)

fields = event.value._pb.fields

fields["type"].string_value = "TASK_CREATED"
fields["entity_id"].string_value = "local-test"
fields["status"].string_value = "PENDING"
fields["processed"].boolean_value = False
fields["event_id"].string_value = EVENT_ID
fields["attempt_count"].integer_value = 0
fields["max_attempts"].integer_value = 3

payload = fields["payload"].map_value.fields

payload["project_id"].string_value = "cloud-test-project"
payload["task_title"].string_value = "Local event-driven test"
payload["task_type"].string_value = "test"


# 3. Send it to the local worker
response = requests.post(
    "http://127.0.0.1:8081/",
    data=event._pb.SerializeToString(),
    headers={"Content-Type": "application/protobuf"},
)

print("Status:", response.status_code)
print("Response:", response.text)