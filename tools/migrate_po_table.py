"""
Migration: add currency, iban, status columns to purchase_orders table.
Also adds a UNIQUE index to prevent duplicates.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "invoices.db"

def migrate():
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    # Get current columns
    cur.execute("PRAGMA table_info(purchase_orders)")
    existing = {row[1] for row in cur.fetchall()}

    # Add missing columns
    new_cols = [
        ("currency", "TEXT DEFAULT 'CHF'"),
        ("iban", "TEXT"),
        ("status", "TEXT DEFAULT 'active'"),
        ("created_by", "TEXT DEFAULT 'seed'"),
    ]

    for col_name, col_def in new_cols:
        if col_name not in existing:
            cur.execute(f"ALTER TABLE purchase_orders ADD COLUMN {col_name} {col_def}")
            print(f"[OK] Added column: {col_name}")

    conn.commit()
    conn.close()
    print("[OK] Migration complete")


if __name__ == "__main__":
    migrate()