from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
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

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text='Открыть приложение',
                    web_app=WebAppInfo(url=settings.app_url),
                ),
            ],
        ],
    )

    await message.answer(
        'Привет! Я буду помогать тебе повторять английские слова.',
        reply_markup=keyboard,
    )
