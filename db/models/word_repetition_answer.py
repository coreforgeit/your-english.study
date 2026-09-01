import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from db.models.base import Base
from enums import LearnedWordStatus


class WordRepetitionAnswer(Base):
    __tablename__ = 'word_repetition_answers'
    __table_args__ = (
        sa.Index(
            'ix_word_repetition_answers_user_word_correct_created',
            'user_id',
            'word_id',
            'is_correct',
            'created_at',
        ),
        sa.Index(
            'ix_word_repetition_answers_user_word_created_id',
            'user_id',
            'word_id',
            'created_at',
            'id',
        ),
    )

    user_id: Mapped[int] = mapped_column(
        sa.ForeignKey('users.id', ondelete='CASCADE'),
    )
    word_id: Mapped[int] = mapped_column(
        sa.ForeignKey('words_en.id', ondelete='CASCADE'),
    )
    session_id: Mapped[str] = mapped_column(
        sa.String(64),
        nullable=False,
        index=True,
    )
    is_correct: Mapped[bool] = mapped_column(sa.Boolean)
    word_status: Mapped[LearnedWordStatus] = mapped_column(
        sa.Enum(
            LearnedWordStatus,
            name='word_repetition_answer_word_status',
            native_enum=False,
            create_constraint=True,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
            length=50,
        ),
        default=LearnedWordStatus.NEW,
        server_default=LearnedWordStatus.NEW,
    )
