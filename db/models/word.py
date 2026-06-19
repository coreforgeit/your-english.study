import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.models.base import Base
from db.models.enums import WordCountry, WordStatus


class Word(Base):
    __tablename__ = 'words'
    __table_args__ = (
        sa.UniqueConstraint(
            'word',
            'part_of_speech',
            name='uq_words_word_part_of_speech',
        ),
    )

    word: Mapped[str] = mapped_column(sa.String(255), index=True)
    pronunciation: Mapped[str | None] = mapped_column(sa.String(255))
    translation: Mapped[str] = mapped_column(sa.String(255))
    part_of_speech: Mapped[str | None] = mapped_column(sa.String(100))
    country: Mapped[WordCountry] = mapped_column(
        sa.Enum(
            WordCountry,
            name='word_country',
            native_enum=False,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        default=WordCountry.BOTH,
        server_default=WordCountry.BOTH,
    )
    level: Mapped[str | None] = mapped_column(sa.String(50))
    audio_url: Mapped[str | None] = mapped_column(sa.String(500))
    audio_file_name: Mapped[str | None] = mapped_column(sa.String(255))
    audio_tg_id: Mapped[str | None] = mapped_column(sa.String(255))
    source: Mapped[str] = mapped_column(
        sa.String(255),
        default='default',
        server_default='default',
    )
    status: Mapped[WordStatus] = mapped_column(
        sa.Enum(
            WordStatus,
            name='word_status',
            native_enum=False,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        default=WordStatus.ALLOWED,
        server_default=WordStatus.ALLOWED.value,
    )

    learned_by_users: Mapped[list['LearnedWord']] = relationship(
        back_populates='word',
        cascade='all, delete-orphan',
    )
