"""Auth routes: signup (creates tenant + membership), login, logout, me.

Guardrail 1: passwords are hashed with Argon2id; plaintext is never logged
or returned. The /me response excludes `password_hash`.
Guardrail 3: on login the server picks the tenant from the user's memberships;
the client cannot pass a tenant id.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ..db import SessionLocal
from ..deps import SESSION_COOKIE, current_user
from ..models import Membership, Tenant, User
from ..security import create_session_token, hash_password, verify_password
from ..settings import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])


def _db() -> Session:
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


class SignupIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=256)
    display_name: str = Field(min_length=1, max_length=120)
    tenant_name: str = Field(min_length=1, max_length=120)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class MeOut(BaseModel):
    id: UUID
    email: EmailStr
    display_name: str
    tenant_id: UUID


def _issue_cookie(response: Response, user_id: UUID, tenant_id: UUID) -> None:
    token = create_session_token(user_id, tenant_id)
    settings = get_settings()
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        max_age=settings.session_ttl,
        httponly=True,
        samesite="lax",
        secure=settings.env == "prod",
        path="/",
    )


@router.post("/signup", status_code=status.HTTP_201_CREATED)
def signup(body: SignupIn, response: Response, db: Session = Depends(_db)) -> MeOut:
    existing = db.execute(select(User).where(User.email == body.email)).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="email taken")

    tenant = Tenant(name=body.tenant_name)
    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        display_name=body.display_name,
    )
    db.add_all([tenant, user])
    db.flush()
    # memberships is FORCE RLS: WITH CHECK requires app.tenant_id to match
    # the row's tenant_id. Signup has no session yet, so we set the GUC on
    # this transaction explicitly before inserting the owner membership.
    db.execute(text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant.id)})
    db.add(Membership(user_id=user.id, tenant_id=tenant.id, role="owner"))
    db.commit()

    _issue_cookie(response, user.id, tenant.id)
    return MeOut(id=user.id, email=user.email, display_name=user.display_name, tenant_id=tenant.id)


@router.post("/login")
def login(body: LoginIn, response: Response, db: Session = Depends(_db)) -> MeOut:
    user = db.execute(select(User).where(User.email == body.email)).scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        # Uniform error so email enumeration is harder.
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")

    membership = db.execute(
        select(Membership).where(Membership.user_id == user.id).order_by(Membership.created_at)
    ).scalar_one_or_none()
    if membership is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="no tenant")

    _issue_cookie(response, user.id, membership.tenant_id)
    return MeOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        tenant_id=membership.tenant_id,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> Response:
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me")
def me(user: User = Depends(current_user)) -> MeOut:
    # Guardrail 1: never leak password_hash.
    # Pull tenant_id from the verified session via the dependency chain by
    # re-resolving current_identity — but we already have it through the
    # membership check inside current_user. For simplicity, look it up:
    from ..db import SessionLocal as _S

    s = _S()
    try:
        m = s.execute(select(Membership).where(Membership.user_id == user.id)).scalar_one()
    finally:
        s.close()
    return MeOut(id=user.id, email=user.email, display_name=user.display_name, tenant_id=m.tenant_id)
