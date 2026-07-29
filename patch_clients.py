import re

with open('planner_service/api/clients.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update get_clients
old_get_clients = """@router.get("", response_model=List[ClientResponse])
async def get_clients(
    q: str = "",
    active_only: bool = False,
    db: AsyncSession = Depends(get_db),
    auth: dict = Depends(require_auth),
):
    \"\"\"Список клиентов текущего тренера (с поиском по имени/телефону).\"\"\"
    trainer_id = int(auth["sub"])
    query = select(Client).where(Client.trainer_id == trainer_id)
    if active_only:
        query = query.where(Client.is_active == True)
    if q:
        query = query.where(
            Client.full_name.ilike(f"%{q}%") | Client.phone.ilike(f"%{q}%")
        )
    query = query.order_by(Client.full_name)
    result = await db.execute(query)
    return result.scalars().all()"""

new_get_clients = """@router.get("", response_model=List[ClientResponse])
async def get_clients(
    q: str = "",
    active_only: bool = False,
    deleted: bool = False,
    db: AsyncSession = Depends(get_db),
    auth: dict = Depends(require_auth),
):
    \"\"\"Список клиентов текущего тренера (с поиском по имени/телефону).\"\"\"
    trainer_id = int(auth["sub"])
    query = select(Client).where(Client.trainer_id == trainer_id)
    
    if deleted:
        query = query.where(Client.deleted_at.is_not(None))
    else:
        query = query.where(Client.deleted_at.is_(None))
        if active_only:
            query = query.where(Client.is_active == True)
            
    if q:
        query = query.where(
            Client.full_name.ilike(f"%{q}%") | Client.phone.ilike(f"%{q}%")
        )
    query = query.order_by(Client.full_name)
    result = await db.execute(query)
    return result.scalars().all()

@router.delete("/trash/empty")
async def empty_trash(
    db: AsyncSession = Depends(get_db),
    auth: dict = Depends(require_auth),
):
    \"\"\"Очистить корзину удаленных клиентов.\"\"\"
    trainer_id = int(auth["sub"])
    result = await db.execute(
        select(Client).where(Client.trainer_id == trainer_id, Client.deleted_at.is_not(None))
    )
    clients = result.scalars().all()
    for client in clients:
        await db.delete(client)
    await db.commit()
    return {"success": True}

@router.delete("/{client_id}")
async def delete_client(
    client_id: int,
    db: AsyncSession = Depends(get_db),
    auth: dict = Depends(require_auth),
):
    \"\"\"Мягкое удаление клиента (в корзину).\"\"\"
    trainer_id = int(auth["sub"])
    result = await db.execute(
        select(Client).where(Client.id == client_id, Client.trainer_id == trainer_id)
    )
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Клиент не найден")
    client.deleted_at = datetime.utcnow()
    await db.commit()
    return {"success": True}

@router.post("/{client_id}/restore")
async def restore_client(
    client_id: int,
    db: AsyncSession = Depends(get_db),
    auth: dict = Depends(require_auth),
):
    \"\"\"Восстановление клиента из корзины.\"\"\"
    trainer_id = int(auth["sub"])
    result = await db.execute(
        select(Client).where(Client.id == client_id, Client.trainer_id == trainer_id)
    )
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Клиент не найден")
    client.deleted_at = None
    await db.commit()
    return {"success": True}"""

content = content.replace(old_get_clients, new_get_clients)

with open('planner_service/api/clients.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("clients.py updated!")
