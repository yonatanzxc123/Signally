"""
Database session management.

This file creates the SQLAlchemy engine and session factory.
Using SQLAlchemy sessions now makes the project cleaner and much easier
to migrate from SQLite to PostgreSQL later.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from signally.config import DATABASE_URL

# SQLite needs this option when used from different contexts/threads.
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, echo=False, future=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
