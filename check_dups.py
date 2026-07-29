import sys, re

files = ['planner_service/api/appointments.py', 'planner_service/api/clients.py', 'planner_service/api/finances.py']
pattern = re.compile(r'^(class |async def |def )([A-Za-z0-9_]+)')

for f in files:
    seen = {}
    with open(f, 'r', encoding='utf8') as file:
        for line in file:
            m = pattern.search(line)
            if m:
                name = m.group(0)
                seen[name] = seen.get(name, 0) + 1
    dups = {k: v for k, v in seen.items() if v > 1}
    if dups:
        print(f'{f} HAS DUPLICATES: {dups}')
    else:
        print(f'{f} is clean.')
