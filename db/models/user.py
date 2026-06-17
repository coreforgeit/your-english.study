import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as psql
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.models.base import Base


class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(
        sa.BigInteger,
        primary_key=True,
        autoincrement=False,
        sort_order=-100,
    )
    full_name: Mapped[str] = mapped_column(sa.String(255))
    username: Mapped[str | None] = mapped_column(sa.String(255))

    words: Mapped[list['UserWord']] = relationship(
        back_populates='user',
        cascade='all, delete-orphan',
    )

    @classmethod
    async def add_or_update(
        cls,
        session: AsyncSession,
        user_id: int,
        full_name: str,
        username: str | None,
    ) -> int:
        stmt = (
            psql.insert(cls)
            .values(
                id=user_id,
                full_name=full_name,
                username=username,
            )
            .on_conflict_do_update(
                index_elements=[cls.id],
                set_={
                    'full_name': full_name,
                    'username': username,
                    'updated_at': sa.func.now(),
                },
            )
            .returning(cls.id)
        )

        result = await session.execute(stmt)
        return result.scalar_one()
