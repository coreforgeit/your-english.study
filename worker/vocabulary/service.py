import logging

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ai.schemas import VocabularyReviewResult, VocabularySynonym
from ai.vocabulary import review_vocabulary_word
from db.models import WordEn, WordEnSynonym, WordRu, WordStatus
from worker.vocabulary.dictionary_api import get_dictionary_word_data


logger = logging.getLogger(__name__)


class VocabularyWordNotFoundError(Exception):
    """Raised when a vocabulary review target no longer exists."""


class VocabularyReviewService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def review(self, word_id: int) -> None:
        word = await self.session.scalar(
            select(WordEn)
            .where(WordEn.id == word_id)
            .options(selectinload(WordEn.translations)),
        )
        if word is None:
            raise VocabularyWordNotFoundError(f'Word {word_id} not found')

        if not word.audio_url:
            dictionary_data = await get_dictionary_word_data(word.word)
            if dictionary_data.audio_url:
                word.audio_url = dictionary_data.audio_url
            if dictionary_data.pronunciation:
                word.pronunciation = dictionary_data.pronunciation

        review = await review_vocabulary_word(
            word=word.word,
            part_of_speech=word.part_of_speech,
        )

        self._replace_translations(word, review)
        await self._link_synonyms(word, review.synonyms)

        word.is_reviewed = True
        word.status = (
            WordStatus.ALLOWED if review.is_appropriate else WordStatus.FORBIDDEN
        )
        await self.session.flush()

        logger.info(
            'Проверка слова завершена: word_id=%s status=%s',
            word.id,
            word.status,
        )

    @staticmethod
    def _replace_translations(
        word: WordEn,
        review: VocabularyReviewResult,
    ) -> None:
        translations = _unique_values(review.translations)
        existing_keys = {
            translation.word.casefold() for translation in word.translations
        }
        for value in translations:
            key = value.casefold()
            if key in existing_keys:
                continue

            word.translations.append(WordRu(word=value))
            existing_keys.add(key)

    async def _link_synonyms(
        self,
        word: WordEn,
        synonyms: list[VocabularySynonym],
    ) -> None:
        seen: set[tuple[str, str]] = set()
        for synonym in synonyms:
            synonym_word = synonym.word.strip()
            synonym_part = synonym.part_of_speech.strip()
            key = (synonym_word.casefold(), synonym_part.casefold())
            if not synonym_word or not synonym_part or key in seen:
                continue
            seen.add(key)

            found_word = await self.session.scalar(
                select(WordEn).where(
                    func.lower(WordEn.word) == synonym_word.casefold(),
                    func.lower(WordEn.part_of_speech) == synonym_part.casefold(),
                ),
            )
            if found_word is None:
                await self._request_missing_word_creation(synonym)
                continue
            if found_word.id == word.id:
                continue

            existing_link = await self.session.scalar(
                select(WordEnSynonym.id).where(
                    or_(
                        and_(
                            WordEnSynonym.word_en_id == word.id,
                            WordEnSynonym.synonym_word_en_id == found_word.id,
                        ),
                        and_(
                            WordEnSynonym.word_en_id == found_word.id,
                            WordEnSynonym.synonym_word_en_id == word.id,
                        ),
                    ),
                ),
            )
            if existing_link is None:
                self.session.add(
                    WordEnSynonym(
                        word_en_id=word.id,
                        synonym_word_en_id=found_word.id,
                    ),
                )

    @staticmethod
    async def _request_missing_word_creation(
        synonym: VocabularySynonym,
    ) -> None:
        # TODO: enqueue the vocabulary word creation process.
        logger.info(
            'Синоним отсутствует в базе, вызвана заглушка добавления: word=%s part_of_speech=%s',
            synonym.word,
            synonym.part_of_speech,
        )


def _unique_values(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = value.strip()
        key = normalized.casefold()
        if normalized and key not in seen:
            seen.add(key)
            result.append(normalized)
    return result
