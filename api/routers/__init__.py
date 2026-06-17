from fastapi import APIRouter

from api.routers.telegram_app import router as telegram_app_router

api_router = APIRouter()
api_router.include_router(telegram_app_router)

__all__ = ('api_router',)
