"""
Migration: create the `analyses` table to store every invoice analysis.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "invoices.db"


def migrate():
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS analyses (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            source TEXT DEFAULT 'chat',
            document_type TEXT,
            document_reference TEXT,
            supplier_name TEXT,
            amount REAL,
            currency TEXT,
            vat REAL,
            po_reference TEXT,
            fields_json TEXT,
            fraud_json TEXT,
            risk_score INTEGER,
            risk_level TEXT,
            decision TEXT,
            raw_text TEXT
        )
    """)

    conn.commit()
    conn.close()
    print("[OK] Table 'analyses' creee")


if __name__ == "__main__":
    migrate()