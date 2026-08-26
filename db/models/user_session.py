import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.models.base import Base


class UserSession(Base):
    __tablename__ = 'user_sessions'

    session_id: Mapped[str] = mapped_column(
        sa.String(64),
        unique=True,
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        sa.ForeignKey('users.id', ondelete='CASCADE'),
        index=True,
    )

    user: Mapped['User'] = relationship(back_populates='sessions')
