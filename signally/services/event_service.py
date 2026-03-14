"""
Service for writing and reading events.

Keeping event logic in its own service makes it easy to later replace
logging destinations or mirror events into Redis / message queues.
"""

from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from signally.models.event import Event


class EventService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def log_event(self, event_type: str, details: str, device_mac: str | None = None) -> Event:
        event = Event(event_type=event_type, details=details, device_mac=device_mac)
        self.session.add(event)
        self.session.commit()
        self.session.refresh(event)
        return event

    def list_recent_events(self, limit: int = 50) -> list[Event]:
        stmt = select(Event).order_by(desc(Event.created_at)).limit(limit)
        return list(self.session.scalars(stmt).all())
