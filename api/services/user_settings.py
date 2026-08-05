import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import UserSettings


class UserSettingsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_for_user(self, user_id: int) -> UserSettings | None:
        return await self.session.scalar(
            sa.select(UserSettings).where(UserSettings.user_id == user_id),
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
