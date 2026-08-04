from __future__ import annotations

import hmac
import logging
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.routes import router
from app.config import get_settings
from app.db import SessionLocal
from app.services.errors import ServiceError

logger = logging.getLogger(__name__)
settings = get_settings()

app = FastAPI(
    title="Aletheia Policy CI API",
    version="0.1.0",
    description="Source-linked policy compilation and repeatable release evaluation evidence.",
    docs_url=None if settings.hosted_mode else "/docs",
    redoc_url=None if settings.hosted_mode else "/redoc",
    openapi_url=None if settings.hosted_mode else "/openapi.json",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_origin],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Idempotency-Key",
        "X-Aletheia-Origin-Token",
        "X-Request-ID",
        "X-Demo-Reset-Secret",
    ],
    expose_headers=["Location", "X-Request-ID"],
)
app.include_router(router)


def _is_hosted_document_upload(request: Request) -> bool:
    parts = request.url.path.rstrip("/").split("/")
    return (
        request.method.upper() == "POST"
        and len(parts) == 6
        and parts[1:4] == ["api", "v1", "projects"]
        and bool(parts[4])
        and parts[5] == "documents"
    )


def _enforce_hosted_api_boundary(request: Request) -> None:
    """Reject direct-origin requests before Starlette parses their bodies."""

    if not settings.hosted_mode or not request.url.path.startswith("/api/v1/"):
        return
    supplied_origin_token = request.headers.get("x-aletheia-origin-token", "")
    if not supplied_origin_token or not hmac.compare_digest(
        supplied_origin_token, settings.api_origin_token
    ):
        raise ServiceError(
            "origin_not_allowed",
            "This API is available through the configured application origin.",
            status_code=403,
        )
    authorization = request.headers.get("authorization", "")
    scheme, separator, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not separator or not token.strip():
        raise ServiceError(
            "authentication_required",
            "A valid user session is required.",
            status_code=401,
            headers={"WWW-Authenticate": "Bearer"},
        )
    if _is_hosted_document_upload(request):
        raise ServiceError(
            "uploads_disabled_in_hosted_workspace",
            "Uploads are disabled in hosted workspaces.",
            status_code=403,
        )


@app.middleware("http")
async def request_context(request: Request, call_next):  # type: ignore[no-untyped-def]
    request_id = request.headers.get("x-request-id", str(uuid4()))
    try:
        _enforce_hosted_api_boundary(request)
        response = await call_next(request)
    except ServiceError as error:
        response = JSONResponse(
            status_code=error.status_code,
            content={
                "code": error.code,
                "message": error.message,
                "details": error.details,
                "request_id": request_id,
            },
            headers=error.headers,
        )
    except Exception:
        logger.exception("Unhandled API error", extra={"request_id": request_id})
        response = JSONResponse(
            status_code=500,
            content={
                "code": "internal_error",
                "message": "The request could not be completed.",
                "details": {},
                "request_id": request_id,
            },
        )
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if settings.hosted_mode:
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; base-uri 'none'; frame-ancestors 'none'"
        )
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    else:
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; connect-src 'self' http://localhost:8000; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline' 'unsafe-eval'"
        )
    return response


@app.exception_handler(ServiceError)
async def service_error_handler(request: Request, error: ServiceError) -> JSONResponse:
    request_id = request.headers.get("x-request-id", str(uuid4()))
    return JSONResponse(
        status_code=error.status_code,
        content={
            "code": error.code,
            "message": error.message,
            "details": error.details,
            "request_id": request_id,
        },
        headers=error.headers,
    )


@app.get("/healthz", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "aletheia-api"}


@app.get("/readyz", tags=["system"])
async def ready() -> dict[str, str]:
    async with SessionLocal() as session:
        await session.execute(text("SELECT 1"))
    return {"status": "ready"}
