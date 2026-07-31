from dataclasses import dataclass
from decimal import Decimal

from enums import TextModel


TOKENS_PER_MILLION = Decimal(1_000_000)


@dataclass(frozen=True, slots=True)
class TextModelPricing:
    input_per_million: Decimal
    cached_input_per_million: Decimal
    output_per_million: Decimal


TEXT_MODEL_PRICING: dict[TextModel, TextModelPricing] = {
    TextModel.GPT_5_6_SOL: TextModelPricing(
        input_per_million=Decimal('5'),
        cached_input_per_million=Decimal('0.5'),
        output_per_million=Decimal('30'),
    ),
    TextModel.GPT_5_6_TERRA: TextModelPricing(
        input_per_million=Decimal('2.5'),
        cached_input_per_million=Decimal('0.25'),
        output_per_million=Decimal('15'),
    ),
    TextModel.GPT_5_6_LUNA: TextModelPricing(
        input_per_million=Decimal('1'),
        cached_input_per_million=Decimal('0.1'),
        output_per_million=Decimal('6'),
    ),
    TextModel.GPT_5_4_NANO: TextModelPricing(
        input_per_million=Decimal('0.2'),
        cached_input_per_million=Decimal('0.02'),
        output_per_million=Decimal('1.25'),
    ),
    TextModel.GPT_5_MINI: TextModelPricing(
        input_per_million=Decimal('0.25'),
        cached_input_per_million=Decimal('0.025'),
        output_per_million=Decimal('2'),
    ),
    TextModel.GPT_5_NANO: TextModelPricing(
        input_per_million=Decimal('0.05'),
        cached_input_per_million=Decimal('0.005'),
        output_per_million=Decimal('0.4'),
    ),
    TextModel.GPT_4O_MINI: TextModelPricing(
        input_per_million=Decimal('0.15'),
        cached_input_per_million=Decimal('0.075'),
        output_per_million=Decimal('0.6'),
    ),
}


def calculate_text_request_cost(
    *,
    model: TextModel,
    input_tokens: int,
    cached_input_tokens: int,
    output_tokens: int,
) -> Decimal:
    if min(input_tokens, cached_input_tokens, output_tokens) < 0:
        raise ValueError('Количество токенов не может быть отрицательным')
    if cached_input_tokens > input_tokens:
        raise ValueError('Кешированных токенов не может быть больше входящих')

    pricing = TEXT_MODEL_PRICING[model]
    uncached_input_tokens = input_tokens - cached_input_tokens

    return (
        Decimal(uncached_input_tokens) * pricing.input_per_million
        + Decimal(cached_input_tokens) * pricing.cached_input_per_million
        + Decimal(output_tokens) * pricing.output_per_million
    ) / TOKENS_PER_MILLION
