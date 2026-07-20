import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.models.base import Base


class WordEnSynonym(Base):
    __tablename__ = 'word_en_synonyms'
    __table_args__ = (
        sa.UniqueConstraint(
            'word_en_id',
            'synonym_word_en_id',
            name='uq_word_en_synonyms_word_en_id_synonym_word_en_id',
        ),
        sa.CheckConstraint(
            'word_en_id <> synonym_word_en_id',
            name='ck_word_en_synonyms_not_self',
        ),
    )

    word_en_id: Mapped[int] = mapped_column(sa.ForeignKey('words_en.id', ondelete='CASCADE'), index=True)
    synonym_word_en_id: Mapped[int] = mapped_column(
        sa.ForeignKey('words_en.id', ondelete='CASCADE'), index=True,
    )

    word_en: Mapped['WordEn'] = relationship(back_populates='synonym_links', foreign_keys=[word_en_id])
    synonym_word_en: Mapped['WordEn'] = relationship(
        back_populates='synonym_of_links', foreign_keys=[synonym_word_en_id],
    )
