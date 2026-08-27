from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.models.base import Base
from enums import LearnedWordStatus


class LearnedWord(Base):
    __tablename__ = 'learned_words'
    __table_args__ = (
        sa.UniqueConstraint(
            'user_id',
            'word_id',
            name='uq_learned_words_user_id_word_id',
        ),
    )

    user_id: Mapped[int] = mapped_column(
        sa.ForeignKey('users.id', ondelete='CASCADE'),
        index=True,
    )
    word_id: Mapped[int] = mapped_column(
        sa.ForeignKey('words_en.id', ondelete='CASCADE'),
        index=True,
    )
    session_id: Mapped[str] = mapped_column(
        sa.String(64),
        nullable=False,
        index=True,
    )
    review_count: Mapped[int] = mapped_column(
        sa.Integer,
        default=0,
        server_default='0',
    )
    status: Mapped[LearnedWordStatus] = mapped_column(
        sa.Enum(
            LearnedWordStatus,
            name='learned_word_status',
            native_enum=False,
            create_constraint=True,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
            length=50,
        ),
        default=LearnedWordStatus.NEW,
        server_default=LearnedWordStatus.NEW,
    )
    last_reviewed_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True),

    )

    user: Mapped['User'] = relationship(back_populates='learned_words')
    word: Mapped['WordEn'] = relationship(back_populates='learned_by_users')
