"""
User and ownership business logic.
"""

from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from signally.models.device import Device, DeviceStatus
from signally.models.user import DeviceOwner, User, UserRole
from signally.utils.time_utils import utc_now


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

    def get_device_owner(self, mac_address: str) -> Optional[User]:
        stmt = (
            select(User)
            .join(DeviceOwner, DeviceOwner.user_id == User.id)
            .where(DeviceOwner.mac_address == mac_address.upper())
        )
        return self.session.scalar(stmt)

    def assign_device_to_user(
        self,
        mac_address: str,
        user_id: int,
        mark_authorized: bool = True,
    ) -> Device:
        normalized_mac = mac_address.upper()
        user = self.get_user(user_id)
        if user is None:
            raise ValueError("User with id {0} was not found".format(user_id))

        device = self.session.scalar(
            select(Device).where(Device.mac_address == normalized_mac)
        )
        if device is None:
            raise ValueError("Device with MAC {0} was not found".format(normalized_mac))

        owner = self.session.scalar(
            select(DeviceOwner).where(DeviceOwner.mac_address == normalized_mac)
        )
        if owner is None:
            owner = DeviceOwner(mac_address=normalized_mac, user_id=user.id)
            self.session.add(owner)
        else:
            owner.user_id = user.id
            owner.assigned_at = utc_now()

        if mark_authorized:
            device.status = DeviceStatus.AUTHORIZED
            device.last_seen = utc_now()

        self.session.commit()
        self.session.refresh(device)
        return device

    def create_user_for_device(
        self,
        mac_address: str,
        display_name: str,
        role: UserRole | str,
    ) -> tuple[User, Device]:
        user = self.create_user(display_name=display_name, role=role)
        device = self.assign_device_to_user(
            mac_address=mac_address,
            user_id=user.id,
            mark_authorized=True,
        )
        return user, device

    def delete_all_device_owners(self) -> int:
        owners = list(self.session.scalars(select(DeviceOwner)).all())
        count = len(owners)

        for owner in owners:
            self.session.delete(owner)

        self.session.commit()
        return count

    def delete_all_users(self) -> int:
        users = self.list_users()
        count = len(users)

        for user in users:
            self.session.delete(user)

        self.session.commit()
        return count
