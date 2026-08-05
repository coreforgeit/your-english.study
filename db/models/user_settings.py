import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.models.base import Base


class UserSettings(Base):
    __tablename__ = 'user_settings'

    timezone: Mapped[str] = mapped_column(
        sa.String(64),
        default='UTC',
        server_default='UTC',
    )
    user_id: Mapped[int] = mapped_column(
        sa.ForeignKey('users.id', ondelete='CASCADE'),
        unique=True,
    )

    user: Mapped['User'] = relationship(back_populates='settings')
