"""Database initialization helper."""

from signally.db.base import Base
from signally.db.session import engine
from signally.models.device import Device
from signally.models.event import Event
from signally.models.security_mode import SecurityState
from signally.models.user import DeviceOwner, User


def initialize_database() -> None:
    """
    Create database tables if they do not already exist.
    """

    _ = Device, Event, SecurityState, User, DeviceOwner
    Base.metadata.create_all(bind=engine)
