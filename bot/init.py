from aiogram import Bot, Dispatcher

from bot.handlers import main_router
from bot.middlewares.db import DBSessionMiddleware
from core.config import settings
from db.session import async_session_factory


def create_bot() -> Bot:
    if not settings.bot_token or settings.bot_token == 'change_me':
        raise RuntimeError('BOT_TOKEN is not configured')

    return Bot(token=settings.bot_token)


def create_dispatcher() -> Dispatcher:
    dispatcher = Dispatcher()
    dispatcher.update.middleware(DBSessionMiddleware(async_session_factory))
    dispatcher.include_router(main_router)
    return dispatcher
