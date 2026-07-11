import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from signally.db.base import Base
from signally.models.device import Device
from signally.models.event import Event
from signally.models.security_mode import SecurityMode, SecurityState
from signally.models.user import User, UserRole
from signally.services.security_mode_service import SecurityModeService


def build_session_factory():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def test_security_mode_defaults_home_and_persists_between_sessions():
    session_factory = build_session_factory()
    session = session_factory()

    state = SecurityModeService(session).get_state()
    assert state.mode == SecurityMode.HOME

    SecurityModeService(session).set_mode(SecurityMode.AWAY, actor_role=UserRole.ADMIN)
    session.close()

    second_session = session_factory()
    persisted = SecurityModeService(second_session).get_state()

    assert persisted.mode == SecurityMode.AWAY
    assert persisted.updated_by_role == "ADMIN"


def test_security_mode_rejects_guest_operator():
    session = build_session_factory()()

    with pytest.raises(PermissionError):
        SecurityModeService(session).set_mode(SecurityMode.AWAY, actor_role=UserRole.GUEST)


def test_security_mode_rejects_invalid_mode():
    session = build_session_factory()()

    with pytest.raises(ValueError):
        SecurityModeService(session).set_mode("VACATION", actor_role=UserRole.ADMIN)
