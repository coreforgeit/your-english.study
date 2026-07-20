import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.models.base import Base


class WordRu(Base):
    __tablename__ = 'words_ru'
    __table_args__ = (
        sa.UniqueConstraint(
            'word_en_id',
            'word',
            name='uq_words_ru_word_en_id_word',
        ),
    )

    word_en_id: Mapped[int] = mapped_column(
        sa.ForeignKey('words_en.id', ondelete='CASCADE'),
        index=True,
    )
    word: Mapped[str] = mapped_column(sa.String(255), index=True)

    word_en: Mapped['WordEn'] = relationship(back_populates='translations')
