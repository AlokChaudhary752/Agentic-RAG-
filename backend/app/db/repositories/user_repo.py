"""Repository for User and Group identity entities."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import GroupEntity, UserEntity
from app.domain.models import ClassificationLevel, UserPrincipal


class UserRepository:
    """Data access methods for users and organizational groups."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: str) -> UserEntity | None:
        """Fetch user by primary key ID."""
        result = await self.session.execute(
            select(UserEntity)
            .options(selectinload(UserEntity.groups))
            .where(UserEntity.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> UserEntity | None:
        """Fetch user by email."""
        result = await self.session.execute(select(UserEntity).where(UserEntity.email == email))
        return result.scalar_one_or_none()

    async def get_principal(self, user_id: str) -> UserPrincipal | None:
        """Resolve a full UserPrincipal with expanded group memberships."""
        user = await self.get_by_id(user_id)
        if not user or not user.is_active:
            return None

        group_names = [group.id for group in user.groups]
        return UserPrincipal(
            user_id=user.id,
            email=user.email,
            full_name=user.full_name,
            roles=[user.role],
            groups=group_names,
            clearance=ClassificationLevel.from_str(user.clearance),
            tenant_id=user.tenant_id,
        )

    async def upsert_group(
        self,
        group_id: str,
        name: str,
        description: str = "",
        tenant_id: str = "tenant-nimbus-default",
    ) -> GroupEntity:
        """Create or update a department group."""
        result = await self.session.execute(select(GroupEntity).where(GroupEntity.id == group_id))
        group = result.scalar_one_or_none()
        if not group:
            group = GroupEntity(
                id=group_id, name=name, description=description, tenant_id=tenant_id
            )
            self.session.add(group)
        else:
            group.name = name
            group.description = description
        await self.session.flush()
        return group

    async def upsert_user(
        self,
        user_id: str,
        email: str,
        full_name: str,
        hashed_password: str,
        role: str,
        clearance: str,
        group_ids: list[str],
        tenant_id: str = "tenant-nimbus-default",
    ) -> UserEntity:
        """Create or update a user and associate with specified groups."""
        groups: list[GroupEntity] = []
        if group_ids:
            group_res = await self.session.execute(
                select(GroupEntity).where(GroupEntity.id.in_(group_ids))
            )
            groups = list(group_res.scalars().all())

        user = await self.get_by_id(user_id)
        if not user:
            user = UserEntity(
                id=user_id,
                email=email,
                full_name=full_name,
                hashed_password=hashed_password,
                role=role,
                clearance=clearance,
                tenant_id=tenant_id,
                groups=groups,
            )
            self.session.add(user)
        else:
            user.email = email
            user.full_name = full_name
            user.hashed_password = hashed_password
            user.role = role
            user.clearance = clearance
            user.groups = groups

        await self.session.flush()
        return user
