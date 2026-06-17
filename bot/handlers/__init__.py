from aiogram import Router

from bot.handlers.start import router as start_router

main_router = Router(name='main')
main_router.include_router(start_router)

__all__ = ('main_router',)
