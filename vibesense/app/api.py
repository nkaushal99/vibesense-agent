"""Application factory wiring heart + preferences routers together."""

from fastapi import FastAPI

from vibesense.app.db_api import router as preferences_router
from vibesense.app.heart_api import router as heart_router


def create_app() -> FastAPI:
    app = FastAPI(title="VibeSense API")
    app.include_router(heart_router)
    app.include_router(preferences_router)
    return app


app = create_app()


__all__ = ["app", "create_app"]
