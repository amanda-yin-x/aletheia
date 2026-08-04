from __future__ import annotations

import asyncio
import hmac
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import jwt
from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from jwt.exceptions import PyJWTError

from app.config import Settings, get_settings
from app.services.errors import ServiceError

LOCAL_USER_ID = "00000000-0000-0000-0000-000000000001"
LOCAL_USER_EMAIL = "local@aletheia.test"
ALLOWED_JWT_ALGORITHMS = ("ES256", "RS256", "EdDSA")


@dataclass(frozen=True, slots=True)
class AuthIdentity:
    subject: str
    email: str | None
    claims: dict[str, Any]


bearer = HTTPBearer(auto_error=False)


@lru_cache(maxsize=8)
def _jwks_client(url: str) -> PyJWKClient:
    return PyJWKClient(url, cache_keys=True, cache_jwk_set=True, lifespan=300)


def _unauthorized() -> ServiceError:
    return ServiceError(
        "authentication_required",
        "A valid user session is required.",
        status_code=401,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _decode_token(token: str, settings: Settings) -> dict[str, Any]:
    try:
        header = jwt.get_unverified_header(token)
        if header.get("alg") not in ALLOWED_JWT_ALGORITHMS or not header.get("kid"):
            raise _unauthorized()
        signing_key = _jwks_client(settings.supabase_jwks_url).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=list(ALLOWED_JWT_ALGORITHMS),
            issuer=settings.supabase_issuer.rstrip("/"),
            audience=settings.supabase_audience,
            options={"require": ["iss", "aud", "exp", "iat", "sub"]},
        )
    except ServiceError:
        raise
    except (PyJWTError, ValueError, TypeError) as error:
        raise _unauthorized() from error
    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject.strip():
        raise _unauthorized()
    if claims.get("role") != "authenticated" or claims.get("is_anonymous") is True:
        raise _unauthorized()
    return dict(claims)


async def require_identity(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    settings: Settings = Depends(get_settings),
) -> AuthIdentity:
    if settings.local_identity_enabled:
        return AuthIdentity(
            subject=LOCAL_USER_ID,
            email=LOCAL_USER_EMAIL,
            claims={"sub": LOCAL_USER_ID, "role": "authenticated", "local": True},
        )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized()
    claims = await asyncio.to_thread(_decode_token, credentials.credentials, settings)
    email = claims.get("email")
    return AuthIdentity(
        subject=str(claims["sub"]),
        email=email if isinstance(email, str) else None,
        claims=claims,
    )


async def require_origin_token(
    x_aletheia_origin_token: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    if settings.local_identity_enabled:
        return
    supplied = x_aletheia_origin_token or ""
    if not supplied or not hmac.compare_digest(supplied, settings.api_origin_token):
        raise ServiceError(
            "origin_not_allowed",
            "This API is available through the configured application origin.",
            status_code=403,
        )
