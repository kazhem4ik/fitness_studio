from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from planner_service.core.database import get_db
from planner_service.core.security import hash_password, decode_access_token
from planner_service.models.admin import AdminUser

router = APIRouter(prefix="/api/admin", tags=["admin"])

COOKIE_NAME = "planner_token"


# --- Auth dependency (только для admin) ---

async def require_admin(request: Request, db: AsyncSession = Depends(get_db)) -> AdminUser:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Не авторизован")
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Токен истёк")

    result = await db.execute(select(AdminUser).where(AdminUser.id == int(payload["sub"])))
    admin = result.scalar_one_or_none()

    if not admin or not admin.is_active:
        raise HTTPException(status_code=401, detail="Пользователь не найден")
    if admin.role != "admin":
        raise HTTPException(status_code=403, detail="Доступ запрещён: требуется роль admin")

    return admin


# --- Schemas ---

class TrainerCreate(BaseModel):
    login: str
    password: str
    display_name: str
    role: str = "trainer"  # 'trainer' | 'admin'


class TrainerUpdate(BaseModel):
    display_name: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


class TrainerResponse(BaseModel):
    id: int
    login: str
    display_name: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Endpoints ---

@router.get("/trainers", response_model=List[TrainerResponse])
async def list_trainers(
    _admin: AdminUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Список всех пользователей системы."""
    result = await db.execute(select(AdminUser).order_by(AdminUser.created_at))
    return result.scalars().all()


@router.post("/trainers", response_model=TrainerResponse, status_code=201)
async def create_trainer(
    data: TrainerCreate,
    _admin: AdminUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Создать нового тренера или admin."""
    existing = await db.execute(select(AdminUser).where(AdminUser.login == data.login))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Пользователь '{data.login}' уже существует")

    if data.role not in ("trainer", "admin"):
        raise HTTPException(status_code=400, detail="role должна быть 'trainer' или 'admin'")

    user = AdminUser(
        login=data.login,
        hashed_password=hash_password(data.password),
        display_name=data.display_name,
        role=data.role,
        is_active=1,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.put("/trainers/{user_id}", response_model=TrainerResponse)
async def update_trainer(
    user_id: int,
    data: TrainerUpdate,
    _admin: AdminUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Обновить имя, пароль, роль или статус тренера."""
    result = await db.execute(select(AdminUser).where(AdminUser.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    if data.display_name is not None:
        user.display_name = data.display_name
    if data.password is not None:
        user.hashed_password = hash_password(data.password)
    if data.role is not None:
        if data.role not in ("trainer", "admin"):
            raise HTTPException(status_code=400, detail="role должна быть 'trainer' или 'admin'")
        user.role = data.role
    if data.is_active is not None:
        user.is_active = 1 if data.is_active else 0

    await db.commit()
    await db.refresh(user)
    return user


@router.delete("/trainers/{user_id}")
async def delete_trainer(
    user_id: int,
    current_admin: AdminUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Деактивировать тренера (мягкое удаление — не удаляет данные)."""
    if user_id == current_admin.id:
        raise HTTPException(status_code=400, detail="Нельзя деактивировать самого себя")

    result = await db.execute(select(AdminUser).where(AdminUser.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    user.is_active = 0
    await db.commit()
    return {"success": True, "message": f"Пользователь {user.login} деактивирован"}
