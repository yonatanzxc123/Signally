"""
Service for writing and reading events.
"""

from datetime import timedelta
from typing import List, Optional, Sequence

from sqlalchemy import and_, desc, func, select
from sqlalchemy.orm import Session

from signally.models.event import Event
from signally.utils.time_utils import utc_now


class EventService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def log_event(self, event_type: str, details: str, device_mac: Optional[str] = None) -> Event:
        event = Event(event_type=event_type, details=details, device_mac=device_mac)
        self.session.add(event)
        try:
            self.session.commit()
            self.session.refresh(event)
        except Exception:
            self.session.rollback()
            raise
        return event

    def log_event_once(
        self,
        event_type: str,
        details: str,
        device_mac: Optional[str] = None,
        cooldown_seconds: int = 60,
    ) -> Optional[Event]:
        if cooldown_seconds > 0 and self.find_recent_matching_event(
            event_type=event_type,
            details=details,
            device_mac=device_mac,
            window_seconds=cooldown_seconds,
        ):
            return None
        return self.log_event(event_type=event_type, details=details, device_mac=device_mac)

    def find_recent_matching_event(
        self,
        event_type: str,
        details: str,
        device_mac: Optional[str],
        window_seconds: int,
    ) -> Optional[Event]:
        since = utc_now() - timedelta(seconds=window_seconds)
        conditions = [
            Event.event_type == event_type,
            Event.details == details,
            Event.created_at >= since,
        ]
        if device_mac is None:
            conditions.append(Event.device_mac.is_(None))
        else:
            conditions.append(func.upper(Event.device_mac) == device_mac.upper())

        stmt = (
            select(Event)
            .where(and_(*conditions))
            .order_by(desc(Event.created_at))
            .limit(1)
        )
        return self.session.scalar(stmt)

    def list_recent_events(self, limit: int = 50) -> List[Event]:
        stmt = select(Event).order_by(desc(Event.created_at)).limit(limit)
        return list(self.session.scalars(stmt).all())

    def list_recent_events_by_types(
        self,
        event_types: Sequence[str],
        limit: int = 500,
    ) -> List[Event]:
        stmt = (
            select(Event)
            .where(Event.event_type.in_(list(event_types)))
            .order_by(desc(Event.created_at))
            .limit(limit)
        )
        return list(self.session.scalars(stmt).all())

    def list_events_for_device_by_types(
        self,
        device_mac: str,
        event_types: Sequence[str],
        limit: int = 100,
    ) -> List[Event]:
        stmt = (
            select(Event)
            .where(func.upper(Event.device_mac) == device_mac.upper())
            .where(Event.event_type.in_(list(event_types)))
            .order_by(desc(Event.created_at))
            .limit(limit)
        )
        return list(self.session.scalars(stmt).all())

    def delete_all_events(self) -> int:
        events = self.list_recent_events(limit=1000000)
        count = len(events)

        for event in events:
            self.session.delete(event)

        self.session.commit()
        return count
