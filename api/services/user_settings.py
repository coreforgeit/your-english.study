import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from db.models import LanguageLevel, UserSettings


class UserSettingsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_for_user(self, user_id: int) -> UserSettings | None:
        return await self.session.scalar(
            sa.select(UserSettings).where(UserSettings.user_id == user_id),
        )

    async def get_language_levels(self) -> list[LanguageLevel]:
        result = await self.session.scalars(
            sa.select(LanguageLevel).order_by(LanguageLevel.grade),
        )
        return list(result.all())

    async def get_effective_language_level(
        self,
        user_id: int,
    ) -> int | None:
        system_level = aliased(LanguageLevel)
        selected_level = aliased(LanguageLevel)

        return await self.session.scalar(
            sa.select(
                sa.func.coalesce(system_level.grade, selected_level.grade),
            )
            .select_from(UserSettings)
            .outerjoin(
                system_level,
                system_level.id == UserSettings.system_language_level_id,
            )
            .outerjoin(
                selected_level,
                selected_level.id == UserSettings.selected_language_level_id,
            )
            .where(UserSettings.user_id == user_id),
        )

    async def update_for_user(
        self,
        user_id: int,
        values: dict[str, object],
    ) -> UserSettings | None:
        settings = await self.get_for_user(user_id)
        if settings is None:
            return None

        for field, value in values.items():
            setattr(settings, field, value)

        return settings
