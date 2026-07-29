import re

with open('planner_service/api/finances.py', 'r', encoding='utf-8') as f:
    content = f.read()

# get_summary queries
content = content.replace(
    """                Client.trainer_id == trainer_id,""",
    """                Client.trainer_id == trainer_id,\n                Client.deleted_at.is_(None),"""
)

# get_income query
content = content.replace(
    """    query = select(Package, Client.full_name).join(Client, Package.client_id == Client.id).where(
        Client.trainer_id == trainer_id
    )""",
    """    query = select(Package, Client.full_name).join(Client, Package.client_id == Client.id).where(
        and_(Client.trainer_id == trainer_id, Client.deleted_at.is_(None))
    )"""
)

# export_csv query
content = content.replace(
    """    income_query = select(Package, Client.full_name).join(Client, Package.client_id == Client.id).where(
        Client.trainer_id == trainer_id
    )""",
    """    income_query = select(Package, Client.full_name).join(Client, Package.client_id == Client.id).where(
        and_(Client.trainer_id == trainer_id, Client.deleted_at.is_(None))
    )"""
)

with open('planner_service/api/finances.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("finances.py updated!")
