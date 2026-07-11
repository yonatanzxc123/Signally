"""
User business logic — app authentication users only.
"""

from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from signally.models.user import User, UserRole


class UserService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def normalize_role(self, role: UserRole | str) -> UserRole:
        if isinstance(role, UserRole):
            return role
        return UserRole(role.upper())

    def require_admin(self, role: UserRole | str) -> None:
        if self.normalize_role(role) != UserRole.ADMIN:
            raise PermissionError("Only admin users can perform this action")

    def create_user(self, display_name: str, role: UserRole | str) -> User:
        user = User(
            display_name=display_name.strip(),
            role=self.normalize_role(role),
        )
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)
        return user

    def list_users(self) -> List[User]:
        stmt = select(User).order_by(User.role.asc(), User.display_name.asc())
        return list(self.session.scalars(stmt).all())

    def get_user(self, user_id: int) -> Optional[User]:
        stmt = select(User).where(User.id == user_id)
        return self.session.scalar(stmt)

    def delete_all_users(self) -> int:
        users = self.list_users()
        count = len(users)
        for user in users:
            self.session.delete(user)
        self.session.commit()
        return count
