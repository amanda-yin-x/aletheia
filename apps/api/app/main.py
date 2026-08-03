from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.routes import router
from app.config import get_settings
from app.db import SessionLocal, create_schema
from app.services.errors import ServiceError
from app.services.seed import seed_demo


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await create_schema()
    async with SessionLocal() as session:
        await seed_demo(session)
    yield


app = FastAPI(
    title="Aletheia Policy CI API",
    version="0.1.0",
    description="Source-linked policy compilation and repeatable release evaluation evidence.",
    lifespan=lifespan,
)
settings = get_settings()
app.add_middleware(CORSMiddleware, allow_origins=[settings.web_origin], allow_credentials=False, allow_methods=["GET", "POST", "PATCH"], allow_headers=["Content-Type", "X-Request-ID", "X-Demo-Reset-Secret"])
app.include_router(router)


@app.middleware("http")
async def request_context(request: Request, call_next):  # type: ignore[no-untyped-def]
    request_id = request.headers.get("x-request-id", str(uuid4()))
    try:
        response = await call_next(request)
    except ServiceError as error:
        response = JSONResponse(status_code=error.status_code, content={"code": error.code, "message": error.message, "details": error.details, "request_id": request_id})
    except Exception:
        response = JSONResponse(status_code=500, content={"code": "internal_error", "message": "The request could not be completed.", "details": {}, "request_id": request_id})
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Content-Security-Policy"] = "default-src 'self'; connect-src 'self' http://localhost:8000; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline' 'unsafe-eval'"
    return response


@app.exception_handler(ServiceError)
async def service_error_handler(request: Request, error: ServiceError) -> JSONResponse:
    request_id = request.headers.get("x-request-id", str(uuid4()))
    return JSONResponse(status_code=error.status_code, content={"code": error.code, "message": error.message, "details": error.details, "request_id": request_id})


@app.get("/healthz", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "aletheia-api"}


@app.get("/readyz", tags=["system"])
async def ready() -> dict[str, str]:
    async with SessionLocal() as session:
        await session.execute(text("SELECT 1"))
    return {"status": "ready"}
