import re

with open('planner_service/api/appointments.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_query_check = """    query = select(Appointment).where(
        and_(
            Appointment.date == appt_date,
            Appointment.is_cancelled == False,
            Appointment.trainer_id == trainer_id,
        )
    )"""

new_query_check = """    query = select(Appointment).join(Client, Appointment.client_id == Client.id).where(
        and_(
            Appointment.date == appt_date,
            Appointment.is_cancelled == False,
            Appointment.trainer_id == trainer_id,
            Client.deleted_at.is_(None),
        )
    )"""

old_query_get = """    query = select(Appointment).where(
        and_(
            Appointment.is_cancelled == False,
            Appointment.trainer_id == trainer_id,
        )
    )"""

new_query_get = """    query = select(Appointment).join(Client, Appointment.client_id == Client.id).where(
        and_(
            Appointment.is_cancelled == False,
            Appointment.trainer_id == trainer_id,
            Client.deleted_at.is_(None),
        )
    )"""

content = content.replace(old_query_check, new_query_check)
content = content.replace(old_query_get, new_query_get)

with open('planner_service/api/appointments.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("appointments.py updated!")
