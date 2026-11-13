"""Password hashing + JWT session tokens.

Guardrail 1: Argon2id is the only password algorithm; plaintext never leaves
this module.
Guardrail 3: `decode_session_token` returns the user+tenant from signed claims
only — request bodies/queries never override these.
"""
from datetime import UTC, datetime, timedelta
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext

from .settings import get_settings

_pwd = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(plaintext: str) -> str:
    return _pwd.hash(plaintext)


def verify_password(plaintext: str, hashed: str) -> bool:
    return _pwd.verify(plaintext, hashed)


def create_session_token(user_id: UUID, tenant_id: UUID) -> str:
    settings = get_settings()
    now = datetime.now(tz=UTC)
    payload = {
        "sub": str(user_id),
        "tid": str(tenant_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=settings.session_ttl)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_alg)


def decode_session_token(token: str) -> tuple[UUID, UUID]:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_alg])
    except JWTError as exc:
        raise ValueError("invalid session token") from exc
    try:
        return UUID(payload["sub"]), UUID(payload["tid"])
    except (KeyError, ValueError) as exc:
        raise ValueError("malformed session token") from exc
