import re

with open('planner_service/api/public_booking.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update get_slots to join Client and check deleted_at
old_get_slots = """    result = await db.execute(
        select(Appointment).where(
            Appointment.date == d,
            Appointment.trainer_id == trainer_id,
            Appointment.is_cancelled == False,
        )
    )"""

new_get_slots = """    result = await db.execute(
        select(Appointment).join(Client, Appointment.client_id == Client.id).where(
            Appointment.date == d,
            Appointment.trainer_id == trainer_id,
            Appointment.is_cancelled == False,
            Client.deleted_at.is_(None)
        )
    )"""

content = content.replace(old_get_slots, new_get_slots)

# 2. Update create_booking check for conflicts
old_conflict = """    conflict = await db.execute(
        select(Appointment).where(
            Appointment.date == app_date,
            Appointment.trainer_id == req.trainer_id,
            Appointment.time_start < end_time,
            Appointment.time_end > start_time,
            Appointment.is_cancelled == False,
        )
    )"""

new_conflict = """    conflict = await db.execute(
        select(Appointment).join(Client, Appointment.client_id == Client.id).where(
            Appointment.date == app_date,
            Appointment.trainer_id == req.trainer_id,
            Appointment.time_start < end_time,
            Appointment.time_end > start_time,
            Appointment.is_cancelled == False,
            Client.deleted_at.is_(None)
        )
    )"""

content = content.replace(old_conflict, new_conflict)

# 3. Update create_booking client search to restore deleted client if matched
old_client_search = """    result = await db.execute(
        select(Client).where(Client.phone == formatted_phone, Client.trainer_id == req.trainer_id)
    )
    client = result.scalars().first()

    is_new = False
    if not client:
        client = Client(
            full_name=req.client_name,
            phone=formatted_phone,
            is_active=True,
            trainer_id=req.trainer_id,
        )
        db.add(client)
        await db.flush()
        is_new = True"""

new_client_search = """    result = await db.execute(
        select(Client).where(Client.phone == formatted_phone, Client.trainer_id == req.trainer_id)
    )
    client = result.scalars().first()

    is_new = False
    if not client:
        client = Client(
            full_name=req.client_name,
            phone=formatted_phone,
            is_active=True,
            trainer_id=req.trainer_id,
        )
        db.add(client)
        await db.flush()
        is_new = True
    elif client.deleted_at is not None:
        client.deleted_at = None
        client.full_name = req.client_name # update name
        await db.flush()
        is_new = True"""

content = content.replace(old_client_search, new_client_search)

with open('planner_service/api/public_booking.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("public_booking.py updated!")
