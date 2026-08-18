import json

from openai import OpenAIError

from ai.client import get_openai_client
from ai.errors import VocabularyAnswerCheckError
from ai.prompts import VOCABULARY_ANSWER_CHECK_PROMPT
from ai.schemas import VocabularyAnswerCheckResult
from enums import AIRequestInitiator, AIRequestScenario, TextModel
from task_queue.tasks import save_text_model_usage


async def check_vocabulary_answer(
    *,
    source_text: str,
    answer: str,
    source_language: str,
    target_language: str,
    part_of_speech: str | None,
    model: TextModel = TextModel.GPT_4O_MINI,
) -> VocabularyAnswerCheckResult:
    input_data = {
        'source_text': source_text,
        'source_language': source_language,
        'target_language': target_language,
        'part_of_speech': part_of_speech,
        'learner_answer': answer,
    }

    try:
        response = await get_openai_client().responses.parse(
            model=model.value,
            input=[
                {
                    'role': 'system',
                    'content': VOCABULARY_ANSWER_CHECK_PROMPT,
                },
                {
                    'role': 'user',
                    'content': json.dumps(input_data, ensure_ascii=False),
                },
            ],
            text_format=VocabularyAnswerCheckResult,
            max_output_tokens=200,
            store=False,
        )
    except OpenAIError as exc:
        raise VocabularyAnswerCheckError(
            'Не удалось проверить ответ через AI',
        ) from exc

    usage = response.usage
    await save_text_model_usage.kiq(
        model=model.value,
        initiator=AIRequestInitiator.USER.value,
        scenario=AIRequestScenario.WORD_ANSWER_CHECK.value,
        input_tokens=usage.input_tokens,
        cached_input_tokens=usage.input_tokens_details.cached_tokens,
        output_tokens=usage.output_tokens,
        reasoning_tokens=usage.output_tokens_details.reasoning_tokens,
        total_tokens=usage.total_tokens,
    )

    if response.output_parsed is None:
        raise VocabularyAnswerCheckError(
            'AI не вернул структурированный результат проверки ответа',
        )

    return response.output_parsed
