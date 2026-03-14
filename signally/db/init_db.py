"""Database initialization helper."""

from signally.db.base import Base
from signally.db.session import engine
from signally.models.device import Device
from signally.models.event import Event


def initialize_database() -> None:
    """
    Create database tables if they do not already exist, and apply any
    missing column migrations for existing databases.
    """

    _ = Device, Event
    Base.metadata.create_all(bind=engine)
    _migrate(engine)


def _migrate(engine) -> None:
    """Add new columns to existing tables if they are missing."""
    with engine.connect() as conn:
        result = conn.execute(
            __import__("sqlalchemy").text("PRAGMA table_info(devices)")
        )
        existing_columns = {row[1] for row in result}

        if "vendor" not in existing_columns:
            conn.execute(__import__("sqlalchemy").text(
                "ALTER TABLE devices ADD COLUMN vendor TEXT"
            ))
        if "device_type" not in existing_columns:
            conn.execute(__import__("sqlalchemy").text(
                "ALTER TABLE devices ADD COLUMN device_type VARCHAR(50)"
            ))
        conn.commit()
