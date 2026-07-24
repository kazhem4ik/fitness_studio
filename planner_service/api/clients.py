from datetime import date, datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from planner_service.core.database import get_db
from planner_service.core.security import decode_access_token
from planner_service.models.client import Client
from planner_service.models.package import Package
from planner_service.models.appointment import Appointment

router = APIRouter(prefix="/api/clients", tags=["clients"])

COOKIE_NAME = "planner_token"


# --- Auth dependency ---

async def require_auth(request: Request):
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Не авторизован")
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Токен истёк")
    return payload


# --- Schemas ---

class ClientCreate(BaseModel):
    full_name: str
    phone: Optional[str] = None
    notes: Optional[str] = None

class ClientUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None

class PackageCreate(BaseModel):
    sessions_count: int
    amount_paid: Optional[float] = None
    payment_method: Optional[str] = None  # cash / card / transfer
    comment: Optional[str] = None
    purchased_at: Optional[date] = None

class PackageResponse(BaseModel):
    id: int
    client_id: int
    purchased_at: date
    sessions_count: int
    amount_paid: Optional[float]
    payment_method: Optional[str]
    comment: Optional[str]
    created_at: datetime
    model_config = {"from_attributes": True}

class ClientResponse(BaseModel):
    id: int
    full_name: str
    phone: Optional[str]
    notes: Optional[str]
    sessions_balance: int
    is_active: bool
    created_at: datetime
    last_visit_at: Optional[datetime]
    model_config = {"from_attributes": True}

class ClientDetailResponse(ClientResponse):
    packages: List[PackageResponse] = []


# --- Endpoints ---

@router.get("", response_model=List[ClientResponse])
async def get_clients(
    q: str = "",
    active_only: bool = False,
    db: AsyncSession = Depends(get_db),
    _auth: dict = Depends(require_auth),
):
    """Список клиентов (с поиском по имени/телефону)."""
    query = select(Client)
    if active_only:
        query = query.where(Client.is_active == True)
    if q:
        query = query.where(
            Client.full_name.ilike(f"%{q}%") | Client.phone.ilike(f"%{q}%")
        )
    query = query.order_by(Client.full_name)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("", response_model=ClientResponse, status_code=201)
async def create_client(
    data: ClientCreate,
    db: AsyncSession = Depends(get_db),
    _auth: dict = Depends(require_auth),
):
    """Создать карточку клиента."""
    client = Client(**data.model_dump())
    db.add(client)
    await db.commit()
    await db.refresh(client)
    return client


@router.get("/{client_id}", response_model=ClientDetailResponse)
async def get_client(
    client_id: int,
    db: AsyncSession = Depends(get_db),
    _auth: dict = Depends(require_auth),
):
    """Детали клиента: карточка + история абонементов."""
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(Client).options(selectinload(Client.packages)).where(Client.id == client_id)
    )
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Клиент не найден")

    # Сортируем пакеты по дате убывания
    packages = sorted(client.packages, key=lambda p: p.purchased_at, reverse=True)

    resp = ClientDetailResponse.model_validate(client)
    resp.packages = [PackageResponse.model_validate(p) for p in packages]
    return resp


@router.put("/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: int,
    data: ClientUpdate,
    db: AsyncSession = Depends(get_db),
    _auth: dict = Depends(require_auth),
):
    """Обновить карточку клиента."""
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Клиент не найден")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(client, key, value)
    await db.commit()
    await db.refresh(client)

    # Синхронизируем имя/телефон в записях (Appointment)
    from sqlalchemy import update
    if data.full_name is not None or data.phone is not None:
        upd_data = {}
        if data.full_name is not None:
            upd_data["client_name"] = data.full_name
        if data.phone is not None:
            upd_data["client_phone"] = data.phone
        
        await db.execute(
            update(Appointment).where(Appointment.client_id == client_id).values(**upd_data)
        )
        await db.commit()

    return client


@router.post("/{client_id}/packages", response_model=PackageResponse, status_code=201)
async def add_package(
    client_id: int,
    data: PackageCreate,
    db: AsyncSession = Depends(get_db),
    _auth: dict = Depends(require_auth),
):
    """Продать абонемент клиенту — пополнить баланс занятий."""
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Клиент не найден")

    pkg_data = data.model_dump()
    if not pkg_data.get("purchased_at"):
        pkg_data["purchased_at"] = date.today()

    package = Package(client_id=client_id, **pkg_data)
    db.add(package)

    # Пополняем баланс
    client.sessions_balance += data.sessions_count

    await db.commit()
    await db.refresh(package)
    return package


@router.post("/{client_id}/attend/{appointment_id}", response_model=ClientResponse)
async def mark_attended(
    client_id: int,
    appointment_id: int,
    db: AsyncSession = Depends(get_db),
    _auth: dict = Depends(require_auth),
):
    """
    Отметить тренировку как «проведена» — списывает 1 занятие с баланса клиента.
    Идемпотентен: повторный вызов не списывает занятие повторно.
    """
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Клиент не найден")

    appt_result = await db.execute(
        select(Appointment).where(
            Appointment.id == appointment_id,
            Appointment.client_id == client_id,
        )
    )
    appointment = appt_result.scalar_one_or_none()
    if not appointment:
        raise HTTPException(status_code=404, detail="Запись не найдена")

    if not appointment.is_attended:
        appointment.is_attended = True
        appointment.updated_at = datetime.utcnow()

        # Списываем занятие (не уходим в минус)
        if client.sessions_balance > 0:
            client.sessions_balance -= 1

        # Обновляем last_visit_at
        client.last_visit_at = datetime.utcnow()

        await db.commit()

    await db.refresh(client)
    return client


@router.get("/{client_id}/appointments", response_model=List[dict])
async def get_client_appointments(
    client_id: int,
    db: AsyncSession = Depends(get_db),
    _auth: dict = Depends(require_auth),
):
    """История записей клиента."""
    result = await db.execute(
        select(Appointment)
        .where(Appointment.client_id == client_id, Appointment.is_cancelled == False)
        .order_by(Appointment.date.desc(), Appointment.time_start.desc())
    )
    appointments = result.scalars().all()
    return [
        {
            "id": a.id,
            "date": str(a.date),
            "time_start": str(a.time_start)[:5],
            "time_end": str(a.time_end)[:5],
            "training_type": a.training_type,
            "is_attended": a.is_attended,
            "is_no_show": a.is_no_show,
            "is_paid": a.is_paid,
            "price": a.price,
        }
        for a in appointments
    ]
