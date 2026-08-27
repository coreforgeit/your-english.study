import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.models.base import Base
from enums import WordCountry, WordSource, WordStatus


class WordEn(Base):
    __tablename__ = 'words_en'
    __table_args__ = (
        sa.UniqueConstraint(
            'word',
            'part_of_speech',
            name='uq_words_en_word_part_of_speech',
        ),
    )

    word: Mapped[str] = mapped_column(sa.String(255), index=True)
    pronunciation: Mapped[str | None] = mapped_column(sa.String(255))
    part_of_speech: Mapped[str | None] = mapped_column(sa.String(100))
    country: Mapped[WordCountry] = mapped_column(
        sa.Enum(
            WordCountry,
            name='word_country',
            native_enum=False,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
            length=50,
        ),
        default=WordCountry.BOTH,
        server_default=WordCountry.BOTH,
    )
    level: Mapped[str | None] = mapped_column(sa.String(50))
    level_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey('language_levels.id', ondelete='RESTRICT'),
        index=True,
    )
    audio_url: Mapped[str | None] = mapped_column(sa.String(500))
    audio_file_name: Mapped[str | None] = mapped_column(sa.String(255))
    audio_tg_id: Mapped[str | None] = mapped_column(sa.String(255))
    source: Mapped[WordSource] = mapped_column(
        sa.Enum(
            WordSource,
            name='word_source',
            native_enum=False,
            create_constraint=True,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
            length=50,
        ),
        default=WordSource.BASE,
        server_default=WordSource.BASE,
    )
    is_reviewed: Mapped[bool] = mapped_column(
        sa.Boolean,
        default=False,
        server_default=sa.false(),
    )
    status: Mapped[WordStatus] = mapped_column(
        sa.Enum(
            WordStatus,
            name='word_status',
            native_enum=False,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
            length=50,
        ),
        default=WordStatus.ALLOWED,
        server_default=WordStatus.ALLOWED,
    )


    language_level: Mapped['LanguageLevel | None'] = relationship(
        back_populates='words',
    )
    translations: Mapped[list['WordRu']] = relationship(
        back_populates='word_en',
        cascade='all, delete-orphan',
        lazy='selectin',
    )
    learned_by_users: Mapped[list['LearnedWord']] = relationship(
        back_populates='word',
        cascade='all, delete-orphan',
    )
    answer_errors: Mapped[list['AnswerError']] = relationship(
        back_populates='word',
        cascade='all, delete-orphan',
    )
    synonym_links: Mapped[list['WordEnSynonym']] = relationship(
        back_populates='word_en',
        cascade='all, delete-orphan',
        foreign_keys='WordEnSynonym.word_en_id',
    )
    synonym_of_links: Mapped[list['WordEnSynonym']] = relationship(
        back_populates='synonym_word_en',
        cascade='all, delete-orphan',
        foreign_keys='WordEnSynonym.synonym_word_en_id',
    )

    @property
    def translation(self) -> str:
        return ', '.join(translation.word for translation in self.translations)

    @property
    def translation_words(self) -> list[str]:
        return [translation.word for translation in self.translations]
