"""Shared Home/Away security mode business logic."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from signally.models.security_mode import SecurityMode, SecurityState
from signally.models.user import UserRole
from signally.utils.time_utils import utc_now


class SecurityModeService:
    STATE_ID = 1

    def __init__(self, session: Session) -> None:
        self.session = session

    def normalize_mode(self, mode: SecurityMode | str) -> SecurityMode:
        if isinstance(mode, SecurityMode):
            return mode
        return SecurityMode(mode.upper())

    def normalize_role(self, role: UserRole | str) -> UserRole:
        if isinstance(role, UserRole):
            return role
        return UserRole(role.upper())

    def require_household_operator(self, role: UserRole | str) -> UserRole:
        normalized = self.normalize_role(role)
        if normalized == UserRole.GUEST:
            raise PermissionError("Guests cannot change Home/Away mode")
        return normalized

    def get_state(self) -> SecurityState:
        state = self.session.scalar(
            select(SecurityState).where(SecurityState.id == self.STATE_ID)
        )
        if state is not None:
            return state

        state = SecurityState(
            id=self.STATE_ID,
            mode=SecurityMode.HOME,
            updated_by_role="SYSTEM",
            updated_at=utc_now(),
        )
        self.session.add(state)
        try:
            self.session.commit()
            self.session.refresh(state)
        except Exception:
            self.session.rollback()
            raise
        return state

    def set_mode(
        self,
        mode: SecurityMode | str,
        actor_role: UserRole | str,
    ) -> SecurityState:
        normalized_role = self.require_household_operator(actor_role)
        state = self.get_state()
        state.mode = self.normalize_mode(mode)
        state.updated_by_role = normalized_role.value
        state.updated_at = utc_now()
        try:
            self.session.commit()
            self.session.refresh(state)
        except Exception:
            self.session.rollback()
            raise
        return state
