from cognitive_canvas.services.event_dispatcher import get_pending_events


events = get_pending_events()

print(f"Found {len(events)} pending events")

for event in events:
    print(event)