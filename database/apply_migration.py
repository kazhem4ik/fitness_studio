"""
Migrates: adds is_blocked column to clients table.
Run once from project root:
    python database/apply_migration.py
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "planner.db"

if not DB_PATH.exists():
    print(f"[ERROR] Database not found: {DB_PATH}")
    exit(1)

conn = sqlite3.connect(str(DB_PATH))
cursor = conn.cursor()

cursor.execute("PRAGMA table_info(clients)")
columns = [row[1] for row in cursor.fetchall()]

if "is_blocked" in columns:
    print("[OK] Column is_blocked already exists - no migration needed.")
else:
    cursor.execute(
        "ALTER TABLE clients ADD COLUMN is_blocked INTEGER NOT NULL DEFAULT 0"
    )
    conn.commit()
    print("[OK] Column is_blocked added to clients table.")

conn.close()
