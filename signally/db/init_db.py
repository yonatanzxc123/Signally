"""Database initialization helper."""

from signally.db.base import Base
from signally.db.session import engine
from signally.models.device import Device
from signally.models.event import Event


def initialize_database() -> None:
    """
    Create database tables if they do not already exist.

    Importing Device and Event ensures SQLAlchemy knows all models before
    calling create_all().
    """

    _ = Device, Event
    Base.metadata.create_all(bind=engine)
