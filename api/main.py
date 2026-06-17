from fastapi import FastAPI

from api.routers import api_router
from api.routers.health import router as health_router

app = FastAPI(title='English Practice API')
app.include_router(health_router)
app.include_router(api_router, prefix='/api')
