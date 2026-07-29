import re

with open('planner_service/api/clients.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_create = """@router.post("", response_model=ClientResponse, status_code=201)
async def create_client(
    data: ClientCreate,
    db: AsyncSession = Depends(get_db),
    auth: dict = Depends(require_auth),
):
    \"\"\"Создать карточку клиента.\"\"\"
    trainer_id = int(auth["sub"])
    client = Client(trainer_id=trainer_id, **data.model_dump())
    db.add(client)
    await db.commit()
    await db.refresh(client)
    return client"""

new_create = """@router.post("", response_model=ClientResponse, status_code=201)
async def create_client(
    data: ClientCreate,
    db: AsyncSession = Depends(get_db),
    auth: dict = Depends(require_auth),
):
    \"\"\"Создать карточку клиента.\"\"\"
    trainer_id = int(auth["sub"])
    
    # Check if client with same name is in trash
    existing = await db.execute(
        select(Client).where(
            Client.full_name == data.full_name,
            Client.trainer_id == trainer_id,
            Client.deleted_at.is_not(None)
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="Клиент с таким именем находится в корзине. Восстановите его в разделе 'Клиенты' (иконка корзины), либо используйте другое имя."
        )
        
    client = Client(trainer_id=trainer_id, **data.model_dump())
    db.add(client)
    await db.commit()
    await db.refresh(client)
    return client"""

content = content.replace(old_create, new_create)

with open('planner_service/api/clients.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("clients.py patched with deleted client warning!")
