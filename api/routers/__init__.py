from fastapi import APIRouter

from api.routers.vocabulary import router as vocabulary_router

api_router = APIRouter()
api_router.include_router(vocabulary_router)

__all__ = ('api_router',)
