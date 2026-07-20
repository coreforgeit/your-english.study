from typing import Any

from ai.client import get_openai_client
from ai.errors import VocabularyReviewError
from ai.prompts import VOCABULARY_REVIEW_PROMPT
from ai.schemas import VocabularyReviewResult
from core.config import settings


async def review_vocabulary_word(
    *,
    word: str,
    part_of_speech: str | None,
) -> VocabularyReviewResult:
    request_options: dict[str, Any] = {}
    if settings.open_ai_vocabulary_review_model.supports_reasoning:
        request_options['reasoning'] = {'effort': 'low'}

    response = await get_openai_client().responses.parse(
        model=settings.open_ai_vocabulary_review_model,
        input=[
            {
                'role': 'system',
                'content': VOCABULARY_REVIEW_PROMPT,
            },
            {
                'role': 'user',
                'content': (
                    f'Word: {word}\n'
                    f'Part of speech: {part_of_speech or "unknown"}'
                ),
            },
        ],
        text_format=VocabularyReviewResult,
        max_output_tokens=1200,
        store=False,
        **request_options,
    )
    if response.output_parsed is None:
        raise VocabularyReviewError(
            f'AI returned no structured review for word {word!r}',
        )

    return response.output_parsed
