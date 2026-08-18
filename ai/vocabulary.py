from typing import Any, TypeVar

from pydantic import BaseModel

from ai.client import get_openai_client
from ai.errors import VocabularyReviewError
from ai.prompts import VOCABULARY_CREATION_PROMPT, VOCABULARY_REVIEW_PROMPT
from ai.schemas import VocabularyCreationResult, VocabularyReviewResult
from enums import AIRequestInitiator, AIRequestScenario, TextModel
from task_queue.tasks import save_text_model_usage


VocabularyResult = TypeVar('VocabularyResult', bound=BaseModel)


async def review_vocabulary_word(
    *,
    word: str,
    part_of_speech: str | None,
    model: TextModel,
    session_id: str | None = None,
) -> VocabularyReviewResult:
    return await _request_vocabulary_analysis(
        word=word,
        part_of_speech=part_of_speech,
        model=model,
        prompt=VOCABULARY_REVIEW_PROMPT,
        result_type=VocabularyReviewResult,
        session_id=session_id,
    )


async def analyze_new_vocabulary_word(
    *,
    word: str,
    part_of_speech_hint: str | None,
    model: TextModel,
    session_id: str | None = None,
) -> VocabularyCreationResult:
    return await _request_vocabulary_analysis(
        word=word,
        part_of_speech=part_of_speech_hint,
        model=model,
        prompt=VOCABULARY_CREATION_PROMPT,
        result_type=VocabularyCreationResult,
        session_id=session_id,
    )


async def _request_vocabulary_analysis(
    *,
    word: str,
    part_of_speech: str | None,
    model: TextModel,
    prompt: str,
    result_type: type[VocabularyResult],
    session_id: str | None,
) -> VocabularyResult:
    request_options: dict[str, Any] = {}
    if model.supports_reasoning:
        request_options['reasoning'] = {'effort': 'low'}

    response = await get_openai_client().responses.parse(
        model=model,
        input=[
            {
                'role': 'system',
                'content': prompt,
            },
            {
                'role': 'user',
                'content': (
                    f'Word: {word}\n'
                    f'Part of speech: {part_of_speech or "unknown"}'
                ),
            },
        ],
        text_format=result_type,
        max_output_tokens=1200,
        store=False,
        **request_options,
    )
    usage = response.usage
    await save_text_model_usage.kiq(
        model=model.value,
        initiator=AIRequestInitiator.SYSTEM.value,
        scenario=AIRequestScenario.WORD_REVIEW.value,
        input_tokens=usage.input_tokens,
        cached_input_tokens=usage.input_tokens_details.cached_tokens,
        output_tokens=usage.output_tokens,
        reasoning_tokens=usage.output_tokens_details.reasoning_tokens,
        total_tokens=usage.total_tokens,
    )

    if response.output_parsed is None:
        raise VocabularyReviewError(
            f'AI returned no structured review for word {word!r}',
        )

    return response.output_parsed
