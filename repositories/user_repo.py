from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from models.user import User, UserRole

class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: int) -> User | None:
        return await self.db.get(User, user_id)

    async def get_by_username(self, username: str) -> User | None:
        u = username.strip()
        # 1. Exact match on username
        result = await self.db.execute(select(User).where(User.username == u))
        user = result.scalars().first()
        if user:
            return user

        # 2. Case-insensitive match on username
        result = await self.db.execute(select(User).where(func.lower(User.username) == u.lower()))
        user = result.scalars().first()
        if user:
            return user

        # 3. Space-to-underscore match (e.g. "Mohamed abdou" -> "mohamed_abdou")
        normalized = u.lower().replace(" ", "_")
        result = await self.db.execute(select(User).where(func.lower(User.username) == normalized))
        user = result.scalars().first()
        if user:
            return user

        # 4. Case-insensitive match on full_name
        result = await self.db.execute(select(User).where(func.lower(User.full_name) == u.lower()))
        user = result.scalars().first()
        if user:
            return user

        # 5. Fallback aliases
        if u.lower() in ("abdou", "198245"):
            result = await self.db.execute(select(User).where(User.username == "mohamed_abdou"))
            user = result.scalars().first()
            if user:
                return user

        return None

    async def create(self, **kwargs) -> User:
        user = User(**kwargs)
        self.db.add(user)
        await self.db.flush()
        return user

    async def get_all(
        self,
        role: UserRole | None = None,
        is_active: bool | None = None,
        gate_number: int | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[User], int]:
        count_stmt = select(func.count()).select_from(User)
        select_stmt = select(User)

        if role is not None:
            count_stmt = count_stmt.where(User.role == role)
            select_stmt = select_stmt.where(User.role == role)
        if is_active is not None:
            count_stmt = count_stmt.where(User.is_active == is_active)
            select_stmt = select_stmt.where(User.is_active == is_active)
        if gate_number is not None:
            count_stmt = count_stmt.where(User.gate_number == gate_number)
            select_stmt = select_stmt.where(User.gate_number == gate_number)

        select_stmt = select_stmt.offset((page - 1) * size).limit(size)

        count_result = await self.db.execute(count_stmt)
        total_count = count_result.scalar_one()

        select_result = await self.db.execute(select_stmt)
        users = list(select_result.scalars().all())

        return users, total_count

    async def update_fields(self, user: User, **fields) -> User:
        for key, value in fields.items():
            setattr(user, key, value)
        await self.db.flush()
        return user
