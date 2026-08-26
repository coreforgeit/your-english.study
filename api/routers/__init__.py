from fastapi import APIRouter

from api.routers.auth_tg import router as auth_tg_router
from api.routers.notifications import router as notifications_router
from api.routers.user_settings import router as user_settings_router
from api.routers.vocabulary import router as vocabulary_router

api_router = APIRouter()
api_router.include_router(auth_tg_router)
api_router.include_router(notifications_router)
api_router.include_router(user_settings_router)
api_router.include_router(vocabulary_router)

__all__ = ('api_router',)
