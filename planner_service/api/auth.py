from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Response, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from planner_service.core.database import get_db
from planner_service.core.security import verify_password, create_access_token, decode_access_token
from planner_service.models.admin import AdminUser

router = APIRouter(prefix="/api/auth", tags=["auth"])

COOKIE_NAME = "planner_token"


class LoginRequest(BaseModel):
    login: str
    password: str


class AuthResponse(BaseModel):
    success: bool
    message: str
    display_name: str | None = None


@router.post("/login", response_model=AuthResponse)
async def login(data: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    """Авторизация по логину и паролю → JWT cookie."""
    result = await db.execute(select(AdminUser).where(AdminUser.login == data.login))
    admin = result.scalar_one_or_none()

    if not admin or not verify_password(data.password, admin.hashed_password):
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")

    token = create_access_token({"sub": str(admin.id), "login": admin.login})

    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=60 * 60 * 24 * 7,  # 7 дней
        path="/clients",
    )

    return AuthResponse(success=True, message="Добро пожаловать!", display_name=admin.display_name)


@router.post("/logout")
async def logout(response: Response):
    """Выход — удаляем cookie."""
    response.delete_cookie(key=COOKIE_NAME, path="/clients")
    return {"success": True, "message": "Вы вышли из системы"}


@router.get("/me")
async def me(request: Request, db: AsyncSession = Depends(get_db)):
    """Проверка текущей авторизации."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Не авторизован")

    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Токен истёк")

    result = await db.execute(select(AdminUser).where(AdminUser.id == int(payload["sub"])))
    admin = result.scalar_one_or_none()

    if not admin:
        raise HTTPException(status_code=401, detail="Пользователь не найден")

    return {
        "id": admin.id,
        "login": admin.login,
        "display_name": admin.display_name,
    }
