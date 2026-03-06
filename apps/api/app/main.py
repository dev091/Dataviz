from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.bootstrap import bootstrap_package_paths
from app.core.config import settings
from app.core.observability import (
    RequestContextLoggingMiddleware,
    RequestMetricsMiddleware,
    configure_logging,
    metrics_text_response,
)
from app.core.security_runtime import RateLimitMiddleware, validate_security_settings
from app.db.init_db import init_db

bootstrap_package_paths()


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()
    validate_security_settings()
    init_db()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestMetricsMiddleware)
app.add_middleware(RequestContextLoggingMiddleware)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": settings.app_name}


@app.get("/metrics")
def metrics():
    return metrics_text_response()


app.include_router(api_router)
