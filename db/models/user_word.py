import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.models.base import Base


class UserWord(Base):
    __tablename__ = 'user_words'
    __table_args__ = (
        sa.UniqueConstraint('user_id', 'word_id', name='uq_user_words_user_id_word_id'),
    )

    user_id: Mapped[int] = mapped_column(
        sa.ForeignKey('users.id', ondelete='CASCADE'),
        index=True,
    )
    word_id: Mapped[int] = mapped_column(
        sa.ForeignKey('words.id', ondelete='CASCADE'),
        index=True,
    )

    user: Mapped['User'] = relationship(back_populates='words')
    word: Mapped['Word'] = relationship(back_populates='users')
