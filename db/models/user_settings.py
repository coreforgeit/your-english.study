from datetime import time

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.models.base import Base
from enums import Timezone


class UserSettings(Base):
    __tablename__ = 'user_settings'

    selected_language_level_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey('language_levels.id', ondelete='SET NULL'),
        index=True,
    )
    system_language_level_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey('language_levels.id', ondelete='SET NULL'),
        index=True,
    )
    reminders_enabled: Mapped[bool] = mapped_column(
        sa.Boolean,
        default=True,
        server_default=sa.true(),
    )
    timezone: Mapped[Timezone | None] = mapped_column(
        sa.String(64),
    )
    reminder_time: Mapped[time] = mapped_column(
        sa.Time,
        default=time(20, 0),
        server_default='20:00:00',
    )
    user_id: Mapped[int] = mapped_column(
        sa.ForeignKey('users.id', ondelete='CASCADE'),
        unique=True,
    )

    user: Mapped['User'] = relationship(back_populates='settings')
    selected_language_level: Mapped['LanguageLevel | None'] = relationship(
        foreign_keys=[selected_language_level_id],
    )
    system_language_level: Mapped['LanguageLevel | None'] = relationship(
        foreign_keys=[system_language_level_id],
    )
