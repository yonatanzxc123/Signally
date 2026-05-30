from __future__ import annotations

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.orm import Session

from signally.config import JWT_ALGORITHM, JWT_EXPIRE_HOURS, JWT_SECRET
from signally.models.user import User, UserRole

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def signup(self, display_name: str, email: str, password: str, role: UserRole) -> dict:
        normalized = email.lower().strip()
        if self.session.scalar(select(User).where(User.email == normalized)):
            raise ValueError("Email already registered")
        user = User(
            display_name=display_name.strip(),
            email=normalized,
            password_hash=_pwd.hash(password),
            role=role,
        )
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)
        return _make_token_response(user)

    def login(self, email: str, password: str) -> dict:
        user = self.session.scalar(select(User).where(User.email == email.lower().strip()))
        if not user or not _pwd.verify(password, user.password_hash):
            raise ValueError("Invalid email or password")
        return _make_token_response(user)


def _make_token_response(user: User) -> dict:
    expire = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS)
    token = jwt.encode(
        {"sub": str(user.id), "role": user.role.value, "display_name": user.display_name, "exp": expire},
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )
    return {
        "token": token,
        "user_id": user.id,
        "display_name": user.display_name,
        "role": user.role.value,
    }


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        raise ValueError("Invalid or expired token")
