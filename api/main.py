from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import api_router
from api.routers.health import router as health_router
from core.config import settings
from core.logging import setup_logging

setup_logging()

app = FastAPI(title='English Practice API')
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)
app.include_router(health_router)
app.include_router(api_router, prefix='/api')
