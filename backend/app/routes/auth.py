from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.foundation import UserAccount
from app.services import auth as auth_svc

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    token: str
    token_type: str = "bearer"
    user_id: UUID
    email: str
    global_role: str | None
    is_admin: bool


class MeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    user_id: UUID
    email: str
    global_role: str | None
    is_admin: bool
    is_active: bool
    last_login: datetime | None
    person_id: UUID | None
    first_name: str | None
    last_name: str | None


class LogoutResponse(BaseModel):
    success: bool


class LogoutAllResponse(BaseModel):
    success: bool
    sessions_revoked: int


@router.post("/login", response_model=LoginResponse)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    user, token = await auth_svc.login(db, data.email, data.password)
    return LoginResponse(
        token=token,
        user_id=user.id,
        email=user.email,
        global_role=user.global_role,
        is_admin=user.is_admin,
    )


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization[7:].strip()
    success = await auth_svc.logout(db, token)
    return LogoutResponse(success=success)


@router.post("/logout-all", response_model=LogoutAllResponse)
async def logout_all(
    user: UserAccount = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Revoke every session belonging to the caller.

    Scoped strictly to ``user.id`` — there is no way to pass another user
    id, and non-admins cannot use this to affect anyone else.
    """
    count = await auth_svc.logout_all_sessions(db, user.id)
    return LogoutAllResponse(success=True, sessions_revoked=count)


@router.get("/me", response_model=MeResponse)
async def me(
    user: UserAccount = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    person = await auth_svc.get_person_for_user(db, user)
    return MeResponse(
        user_id=user.id,
        email=user.email,
        global_role=user.global_role,
        is_admin=user.is_admin,
        is_active=user.is_active,
        last_login=user.last_login,
        person_id=user.person_id,
        first_name=person.first_name if person else None,
        last_name=person.last_name if person else None,
    )
