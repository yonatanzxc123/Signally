"""
Service for writing and reading events.
"""

from typing import List, Optional

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from signally.models.event import Event


class EventService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def log_event(self, event_type: str, details: str, device_mac: Optional[str] = None) -> Event:
        event = Event(event_type=event_type, details=details, device_mac=device_mac)
        self.session.add(event)
        self.session.commit()
        self.session.refresh(event)
        return event

    def list_recent_events(self, limit: int = 50) -> List[Event]:
        stmt = select(Event).order_by(desc(Event.created_at)).limit(limit)
        return list(self.session.scalars(stmt).all())

    def delete_all_events(self) -> int:
        events = self.list_recent_events(limit=1000000)
        count = len(events)

        for event in events:
            self.session.delete(event)

        self.session.commit()
        return count