"""Security headers + simple in-memory per-IP rate limiter.

Production should move the rate limiter to Redis; the in-memory one is fine
for a single uvicorn worker which is also the current deployment target
(see Stage 3 known gaps on horizontal scaling).
"""
from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque

from fastapi import Request, status
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware

from .settings import get_settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        resp: Response = await call_next(request)
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        resp.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' blob: data:; style-src 'self' 'unsafe-inline'; "
            "script-src 'self'; connect-src *; font-src 'self' data:; frame-ancestors 'none'",
        )
        return resp


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Token-bucket-ish per-IP limiter for auth endpoints.

    Why only auth? Chat/editor traffic goes through the websocket, which is
    already a single accepted connection per user and has its own membership
    check. REST hot paths are proportional to human activity (tens/second per
    user max); the risk area for abuse is `/auth/login` + `/auth/signup`.
    """

    WINDOW_SECONDS = 60
    LIMIT = 120  # per window, per IP, for protected routes

    def __init__(self, app):
        super().__init__(app)
        self.hits: dict[str, deque[float]] = defaultdict(deque)
        self.lock = asyncio.Lock()

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path in ("/auth/login", "/auth/signup"):
            ip = request.client.host if request.client else "?"
            now = time.monotonic()
            async with self.lock:
                q = self.hits[ip]
                while q and now - q[0] > self.WINDOW_SECONDS:
                    q.popleft()
                if len(q) >= self.LIMIT:
                    return JSONResponse(
                        {"detail": "rate limited"},
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    )
                q.append(now)
        return await call_next(request)


def startup_assertions() -> None:
    settings = get_settings()
    if settings.jwt_secret in ("", "change-me-to-a-long-random-string"):
        # Fail loudly in production. We don't want a cluster running with the
        # example secret from .env.example.
        import os

        if os.environ.get("ENV", "dev") != "dev":
            raise RuntimeError("JWT_SECRET is not set to a real value")
