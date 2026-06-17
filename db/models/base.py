from datetime import datetime
from typing import Self

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    __abstract__ = True

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, sort_order=-100)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
        sort_order=1000,
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        nullable=False,
        sort_order=1001,
    )

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}(id={getattr(self, "id", None)})>'

    @classmethod
    async def get_by_id(cls, session: AsyncSession, entry_id: int) -> Self | None:
        return await session.get(cls, entry_id)

    @classmethod
    async def get_all(cls, session: AsyncSession) -> list[Self]:
        result = await session.execute(sa.select(cls))
        return list(result.scalars().all())

    @classmethod
    async def update_by_id(
        cls,
        session: AsyncSession,
        entry_id: int,
        **kwargs,
    ) -> None:
        if not kwargs:
            raise ValueError('No fields provided for update')

        stmt = sa.update(cls).where(cls.id == entry_id).values(**kwargs)
        await session.execute(stmt)
