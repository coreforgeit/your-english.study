import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.models.base import Base


class AnswerError(Base):
    __tablename__ = 'answer_errors'

    user_id: Mapped[int] = mapped_column(
        sa.ForeignKey('users.id', ondelete='CASCADE'),
        index=True,
    )
    word_id: Mapped[int] = mapped_column(
        sa.ForeignKey('words.id', ondelete='CASCADE'),
        index=True,
    )
    answer_type: Mapped[str] = mapped_column(sa.String(20))
    answer_language: Mapped[str] = mapped_column(sa.String(10))
    user_answer: Mapped[str] = mapped_column(sa.Text)
    correct_answer: Mapped[str] = mapped_column(sa.Text)
    is_correct: Mapped[bool] = mapped_column(sa.Boolean)
    has_typo: Mapped[bool] = mapped_column(sa.Boolean, default=False, server_default='false')
    typo_type: Mapped[str | None] = mapped_column(sa.String(20))
    typo_index: Mapped[int | None] = mapped_column(sa.Integer)
    expected: Mapped[str | None] = mapped_column(sa.String(10))
    actual: Mapped[str | None] = mapped_column(sa.String(10))

    user: Mapped['User'] = relationship(back_populates='answer_errors')
    word: Mapped['Word'] = relationship(back_populates='answer_errors')
