from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import User


router = Router(name='start')


@router.message(CommandStart())
async def start_handler(message: Message, session: AsyncSession) -> None:
    telegram_user = message.from_user
    if telegram_user is None:
        return

    await User.add_or_update(
        session=session,
        user_id=telegram_user.id,
        full_name=telegram_user.full_name,
        username=telegram_user.username,
    )

    await message.answer('Привет! Я буду помогать тебе повторять английские слова.')
