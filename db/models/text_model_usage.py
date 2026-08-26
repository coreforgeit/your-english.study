from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from db.models.base import Base
from enums import AIRequestInitiator, AIRequestScenario


class TextModelUsage(Base):
    __tablename__ = 'text_model_usages'

    model: Mapped[str] = mapped_column(sa.String(100))
    initiator: Mapped[AIRequestInitiator] = mapped_column(
        sa.Enum(
            AIRequestInitiator,
            name='ai_request_initiator',
            native_enum=False,
            create_constraint=True,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        default=AIRequestInitiator.SYSTEM,
        server_default=AIRequestInitiator.SYSTEM,
    )
    scenario: Mapped[AIRequestScenario] = mapped_column(
        sa.Enum(
            AIRequestScenario,
            name='ai_request_scenario',
            native_enum=False,
            create_constraint=True,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
            length=50
        ),

    )
    input_tokens: Mapped[int] = mapped_column(sa.Integer)
    cached_input_tokens: Mapped[int] = mapped_column(
        sa.Integer,
        default=0,
        server_default='0',
    )
    output_tokens: Mapped[int] = mapped_column(sa.Integer)
    reasoning_tokens: Mapped[int] = mapped_column(
        sa.Integer,
        default=0,
        server_default='0',
    )
    total_tokens: Mapped[int] = mapped_column(sa.Integer)
    cost_usd: Mapped[Decimal] = mapped_column(sa.Numeric(20, 10))
