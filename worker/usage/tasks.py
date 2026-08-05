import logging

from db.models import TextModelUsage
from db.session import async_session_factory
from enums import AIRequestInitiator, AIRequestScenario, TextModel
from worker.broker import broker
from worker.usage.pricing import calculate_text_request_cost


logger = logging.getLogger(__name__)


@broker.task
async def save_text_model_usage(
    *,
    model: str,
    initiator: str,
    scenario: str,
    input_tokens: int,
    cached_input_tokens: int,
    output_tokens: int,
    reasoning_tokens: int,
    total_tokens: int,
    session_id: str | None = None,
) -> None:
    text_model = TextModel(model)
    cost_usd = calculate_text_request_cost(
        model=text_model,
        input_tokens=input_tokens,
        cached_input_tokens=cached_input_tokens,
        output_tokens=output_tokens,
    )

    async with async_session_factory() as session:
        try:
            session.add(
                TextModelUsage(
                    session_id=session_id,
                    model=text_model.value,
                    initiator=AIRequestInitiator(initiator),
                    scenario=AIRequestScenario(scenario),
                    input_tokens=input_tokens,
                    cached_input_tokens=cached_input_tokens,
                    output_tokens=output_tokens,
                    reasoning_tokens=reasoning_tokens,
                    total_tokens=total_tokens,
                    cost_usd=cost_usd,
                ),
            )
            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception(
                'Не удалось сохранить использование текстовой модели: model=%s scenario=%s',
                model,
                scenario,
            )
            raise

    logger.info(
        'Использование текстовой модели сохранено: model=%s scenario=%s tokens=%s cost_usd=%s',
        model,
        scenario,
        total_tokens,
        cost_usd,
    )
