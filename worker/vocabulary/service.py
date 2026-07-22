import logging

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ai.enums import TextModel
from ai.schemas import (
    VocabularyCreationResult,
    VocabularyReviewResult,
    VocabularySynonym,
)
from ai.vocabulary import analyze_new_vocabulary_word, review_vocabulary_word
from db.models import (
    WordEn,
    WordEnSynonym,
    WordRu,
    WordSource,
    WordStatus,
)
from worker.vocabulary.dictionary_api import get_dictionary_word_data


logger = logging.getLogger(__name__)


class VocabularyReviewService:
    def __init__(self, session: AsyncSession, model: TextModel) -> None:
        self.session = session
        self.model = model
        self._processed_words: set[tuple[str, str | None]] = set()

    async def review(self, word_id: int) -> WordEn:
        word: WordEn = await self.session.scalar(
            select(WordEn)
            .where(WordEn.id == word_id)
            .options(selectinload(WordEn.translations)),
        )

        logger.info(f' ')
        logger.info(f'review: {word_id} {word.word}')
        if word is None:
            raise LookupError(f'Слово {word_id} не найдено')

        if word.is_reviewed:
            return word

        await self._fill_dictionary_data(word)
        review = await review_vocabulary_word(
            word=word.word,
            part_of_speech=word.part_of_speech,
            model=self.model,
        )

        self._add_translations(word, review.translations)
        word.level = review.level
        word.is_reviewed = True
        word.status = self._status_from_review(review)
        await self.session.flush()

        logger.info(
            f'review:\n{
            review.translations}\n'
            f'{review.level}\n'
            f'{[[w, p] for w, p in review.synonyms]}'
        )


        for synonym in _unique_synonyms(review.synonyms):
            await self._add_english_word(
                word=synonym.word,
                synonym_of_word_id=word.id,
                part_of_speech_hint=synonym.part_of_speech,
            )

        await self.session.flush()
        return word

    async def add_english_word(
        self,
        word: str,
        synonym_of_word_id: int | None = None,
    ) -> WordEn | None:
        return await self._add_english_word(
            word=word,
            synonym_of_word_id=synonym_of_word_id,
            part_of_speech_hint=None,
        )

    async def _add_english_word(
        self,
        *,
        word: str,
        synonym_of_word_id: int | None,
        part_of_speech_hint: str | None,
    ) -> WordEn | None:
        normalized_word = _normalize_word(word)
        if not normalized_word:
            return None

        logger.info(f'---')
        logger.info(f'_add_english_word: {word} {normalized_word} {part_of_speech_hint}')
        synonym_of = await self._get_word_by_id(synonym_of_word_id)
        if synonym_of:
            logger.info(f'synonym_of: {synonym_of} {synonym_of.word}')

        preferred_part_of_speech = (
            part_of_speech_hint
            or (synonym_of.part_of_speech if synonym_of is not None else None)
        )
        existing_word = await self._find_word(
            word=normalized_word,
            preferred_part_of_speech=preferred_part_of_speech,
        )
        logger.info(f'existing_word: {existing_word}')

        if existing_word is not None:
            if synonym_of is not None:
                await self._ensure_synonym_relation(synonym_of, existing_word)
            return existing_word

        processing_key = (
            normalized_word,
            _normalize_part_of_speech(preferred_part_of_speech),
        )
        logger.info(f'self._processed_words: {self._processed_words}')

        if processing_key in self._processed_words:
            return None
        self._processed_words.add(processing_key)

        dictionary_data = await get_dictionary_word_data(normalized_word)
        analysis = await analyze_new_vocabulary_word(
            word=normalized_word,
            part_of_speech_hint=preferred_part_of_speech,
            model=self.model,
        )
        logger.info(f'analysis:\n{analysis.translations}\n{analysis.level}\n{analysis.synonyms}')
        created_word = self._build_word(
            word=normalized_word,
            analysis=analysis,
            part_of_speech=(
                preferred_part_of_speech or analysis.part_of_speech
            ),
            pronunciation=dictionary_data.pronunciation,
            audio_url=dictionary_data.audio_url,
        )
        self.session.add(created_word)
        await self.session.flush()

        if synonym_of is not None:
            await self._ensure_synonym_relation(synonym_of, created_word)

        for synonym in _unique_synonyms(analysis.synonyms):
            await self._add_english_word(
                word=synonym.word,
                synonym_of_word_id=created_word.id,
                part_of_speech_hint=synonym.part_of_speech,
            )

        logger.info(f'created_word: {created_word}')
        return created_word

    async def _fill_dictionary_data(self, word: WordEn) -> None:
        if word.audio_url:
            return

        dictionary_data = await get_dictionary_word_data(word.word)
        if dictionary_data.audio_url:
            word.audio_url = dictionary_data.audio_url
        if not word.pronunciation and dictionary_data.pronunciation:
            word.pronunciation = dictionary_data.pronunciation

    async def _get_word_by_id(self, word_id: int | None) -> WordEn | None:
        if word_id is None:
            return None

        word = await self.session.get(WordEn, word_id)
        if word is None:
            raise LookupError(f'Слово {word_id} не найдено')
        return word

    async def _find_word(
        self,
        *,
        word: str,
        preferred_part_of_speech: str | None,
    ) -> WordEn | None:
        if preferred_part_of_speech:
            return await self.session.scalar(
                select(WordEn)
                .where(
                    func.lower(WordEn.word) == word.casefold(),
                    func.lower(WordEn.part_of_speech)
                    == _normalize_part_of_speech(preferred_part_of_speech),
                )
                .order_by(WordEn.id),
            )

        return await self.session.scalar(
            select(WordEn).where(func.lower(WordEn.word) == word.casefold()).order_by(WordEn.id),
        )

    async def _ensure_synonym_relation(self, word: WordEn, synonym: WordEn) -> None:
        if word.id == synonym.id:
            return

        existing_link = await self.session.scalar(
            select(WordEnSynonym.id).where(
                or_(
                    and_(
                        WordEnSynonym.word_en_id == word.id,
                        WordEnSynonym.synonym_word_en_id == synonym.id,
                    ),
                    and_(
                        WordEnSynonym.word_en_id == synonym.id,
                        WordEnSynonym.synonym_word_en_id == word.id,
                    ),
                ),
            ),
        )
        if existing_link is None:
            self.session.add(
                WordEnSynonym(
                    word_en_id=word.id,
                    synonym_word_en_id=synonym.id,
                ),
            )

    @staticmethod
    def _build_word(
        *,
        word: str,
        analysis: VocabularyCreationResult,
        part_of_speech: str,
        pronunciation: str | None,
        audio_url: str | None,
    ) -> WordEn:
        return WordEn(
            word=word,
            pronunciation=pronunciation,
            part_of_speech=part_of_speech.strip().casefold(),
            level=analysis.level,
            audio_url=audio_url,
            source=WordSource.GPT,
            is_reviewed=True,
            status=WordStatus.ALLOWED if analysis.is_appropriate else WordStatus.FORBIDDEN,
            translations=[
                WordRu(word=translation) for translation in _unique_values(analysis.translations)
            ],
        )

    @staticmethod
    def _add_translations(word: WordEn, translations: list[str]) -> None:
        existing_keys = {
            translation.word.casefold() for translation in word.translations
        }
        for translation in _unique_values(translations):
            key = translation.casefold()
            if key in existing_keys:
                continue
            word.translations.append(WordRu(word=translation))
            existing_keys.add(key)

    @staticmethod
    def _status_from_review(review: VocabularyReviewResult) -> WordStatus:
        return (
            WordStatus.ALLOWED
            if review.is_appropriate
            else WordStatus.FORBIDDEN
        )


def _normalize_word(word: str) -> str:
    return ' '.join(word.split()).casefold()


def _normalize_part_of_speech(
    part_of_speech: str | None,
) -> str | None:
    if part_of_speech is None:
        return None
    return part_of_speech.strip().casefold() or None


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


def _unique_synonyms(
    synonyms: list[VocabularySynonym],
) -> list[VocabularySynonym]:
    result: list[VocabularySynonym] = []
    seen: set[tuple[str, str]] = set()
    for synonym in synonyms:
        word = _normalize_word(synonym.word)
        part_of_speech = synonym.part_of_speech.strip().casefold()
        key = (word, part_of_speech)
        if word and part_of_speech and key not in seen:
            seen.add(key)
            result.append(
                VocabularySynonym(
                    word=word,
                    part_of_speech=part_of_speech,
                ),
            )
    return result
