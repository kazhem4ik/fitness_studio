import re

with open('planner_service/api/appointments.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update create_appointment
old_create_client = """    client_result = await db.execute(client_query)
    client = client_result.scalar_one_or_none()

    if not client:
        client = Client(
            full_name=data.client_name,
            phone=data.client_phone,
            trainer_id=trainer_id,
        )
        db.add(client)
        await db.commit()
        await db.refresh(client)"""

new_create_client = """    client_result = await db.execute(client_query)
    client = client_result.scalar_one_or_none()
    
    if client and client.deleted_at is not None:
        raise HTTPException(
            status_code=400,
            detail="Данный клиент находится в корзине. Восстановите его в разделе 'Клиенты' (иконка корзины), либо используйте другое имя."
        )

    if not client:
        client = Client(
            full_name=data.client_name,
            phone=data.client_phone,
            trainer_id=trainer_id,
        )
        db.add(client)
        await db.commit()
        await db.refresh(client)"""

content = content.replace(old_create_client, new_create_client)

# 2. Update update_appointment
old_update_client = """        client_result = await db.execute(client_query)
        client = client_result.scalar_one_or_none()

        if not client:
            client = Client(
                full_name=appointment.client_name,
                phone=appointment.client_phone,
                trainer_id=trainer_id,
            )
            db.add(client)
            await db.commit()
            await db.refresh(client)"""

new_update_client = """        client_result = await db.execute(client_query)
        client = client_result.scalar_one_or_none()

        if client and client.deleted_at is not None:
            raise HTTPException(
                status_code=400,
                detail="Данный клиент находится в корзине. Восстановите его в разделе 'Клиенты' (иконка корзины), либо используйте другое имя."
            )

        if not client:
            client = Client(
                full_name=appointment.client_name,
                phone=appointment.client_phone,
                trainer_id=trainer_id,
            )
            db.add(client)
            await db.commit()
            await db.refresh(client)"""

content = content.replace(old_update_client, new_update_client)


with open('planner_service/api/appointments.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("appointments.py patched with deleted client warning!")
