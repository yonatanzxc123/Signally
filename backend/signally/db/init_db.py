"""Database initialization helper."""

from signally.db.base import Base
from signally.db.session import engine
from sqlalchemy import inspect, text

from signally.models.device import Device
from signally.models.event import Event
from signally.models.presence_state import PresenceState
from signally.models.security_mode import SecurityState
from signally.models.user import User


def initialize_database() -> None:
    """
    Create database tables if they do not already exist.
    """

    _ = Device, Event, PresenceState, SecurityState, User
    Base.metadata.create_all(bind=engine)

    # create_all does not add columns to an existing SQLite database.
    if "owner_name" not in {column["name"] for column in inspect(engine).get_columns("devices")}:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE devices ADD COLUMN owner_name VARCHAR(100)"))
