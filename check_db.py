import sqlite3
import os

print("--- root planner.db ---")
try:
    c = sqlite3.connect('planner.db').cursor()
    print("Tables:", [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()])
    print("Clients count:", c.execute("SELECT count(*) FROM clients").fetchone()[0] if 'clients' in [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()] else "No clients table")
except Exception as e: print(e)

print("\n--- database/planner.db ---")
try:
    c = sqlite3.connect('database/planner.db').cursor()
    print("Tables:", [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()])
    print("Clients count:", c.execute("SELECT count(*) FROM clients").fetchone()[0] if 'clients' in [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()] else "No clients table")
except Exception as e: print(e)

print("\n--- database/studio.db ---")
try:
    c = sqlite3.connect('database/studio.db').cursor()
    print("Tables:", [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()])
    print("Clients count:", c.execute("SELECT count(*) FROM clients").fetchone()[0] if 'clients' in [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()] else "No clients table")
except Exception as e: print(e)
