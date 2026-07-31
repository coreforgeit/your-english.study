import logging

import sqlalchemy as sa

from db.models import LearnedWord, WordRepetitionAnswer
from db.session import async_session_factory
from enums import LearnedWordStatus, TextModel
from worker.broker import broker
from worker.vocabulary.service import VocabularyReviewService


logger = logging.getLogger(__name__)


@broker.task
async def record_word_repetition(
    *,
    user_id: int,
    word_id: int,
    is_correct: bool,
) -> None:
    async with async_session_factory() as session:
        try:
            result = await session.execute(
                sa.update(LearnedWord)
                .where(
                    LearnedWord.user_id == user_id,
                    LearnedWord.word_id == word_id,
                )
                .values(
                    review_count=LearnedWord.review_count + 1,
                    last_reviewed_at=sa.func.now(),
                ),
                execution_options={'synchronize_session': False},
            )
            if result.rowcount == 0:
                logger.warning(
                    'Выученное слово для записи повторения не найдено: '
                    'user_id=%s word_id=%s',
                    user_id,
                    word_id,
                )
                await session.rollback()
                return

            session.add(
                WordRepetitionAnswer(
                    user_id=user_id,
                    word_id=word_id,
                    is_correct=is_correct,
                ),
            )
            await session.flush()

            if is_correct:
                correct_days = await session.scalar(
                    sa.select(
                        sa.func.count(
                            sa.distinct(
                                sa.cast(WordRepetitionAnswer.created_at, sa.Date),
                            ),
                        ),
                    ).where(
                        WordRepetitionAnswer.user_id == user_id,
                        WordRepetitionAnswer.word_id == word_id,
                        WordRepetitionAnswer.is_correct.is_(True),
                    ),
                )
                if correct_days >= 3:
                    await session.execute(
                        sa.update(LearnedWord)
                        .where(
                            LearnedWord.user_id == user_id,
                            LearnedWord.word_id == word_id,
                        )
                        .values(status=LearnedWordStatus.LEARNED),
                        execution_options={'synchronize_session': False},
                    )

            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception(
                'Не удалось записать повторение слова: user_id=%s word_id=%s',
                user_id,
                word_id,
            )
            raise

    logger.info(
        'Повторение слова записано: user_id=%s word_id=%s is_correct=%s',
        user_id,
        word_id,
        is_correct,
    )


@broker.task
async def review_word(*, word_id: int, model: str) -> None:
    text_model = TextModel(model)
    logger.info(
        'Задача проверки слова принята: word_id=%s model=%s',
        word_id,
        text_model.value,
    )

    async with async_session_factory() as session:
        try:
            service = VocabularyReviewService(session, text_model)
            await service.review(word_id)
            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception(
                'Проверка слова завершилась ошибкой: word_id=%s model=%s',
                word_id,
                text_model.value,
            )
            raise
