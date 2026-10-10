"""
Database initialization and seeding for the fraud detection system.

Creates SQLite tables and populates them with realistic demo data:
- suppliers: supplier info (IBAN, creation date, blacklist status)
- invoices_history: past invoices for duplicate/pattern detection
- purchase_orders: PO reference data

Author: Anio Joseph
Project: Hack Apertus - October 2026
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "invoices.db"


def get_connection() -> sqlite3.Connection:
    """Return a SQLite connection with row factory."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they don't exist."""
    conn = get_connection()
    cur = conn.cursor()

    # Table fournisseurs
    cur.execute("""
        CREATE TABLE IF NOT EXISTS suppliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            iban TEXT NOT NULL,
            created_at TEXT NOT NULL,
            is_blacklisted INTEGER DEFAULT 0,
            country TEXT DEFAULT 'CH',
            avg_invoice_amount REAL DEFAULT 0,
            invoice_count INTEGER DEFAULT 0
        )
    """)

    # Table historique factures
    cur.execute("""
        CREATE TABLE IF NOT EXISTS invoices_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id TEXT NOT NULL,
            supplier_name TEXT NOT NULL,
            amount REAL NOT NULL,
            vat REAL NOT NULL,
            vat_rate REAL NOT NULL,
            po_reference TEXT,
            iban TEXT,
            issued_at TEXT NOT NULL,
            status TEXT DEFAULT 'pending'
        )
    """)

    # Table bons de commande
    cur.execute("""
        CREATE TABLE IF NOT EXISTS purchase_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            po_reference TEXT UNIQUE NOT NULL,
            supplier_name TEXT NOT NULL,
            amount REAL NOT NULL,
            vat REAL NOT NULL,
            items TEXT,
            created_at TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()
    print(f"[OK] Database initialized at {DB_PATH}")


def seed_data() -> None:
    """Populate with realistic demo data."""
    conn = get_connection()
    cur = conn.cursor()

    # --- Fournisseurs ---
    suppliers = [
        # (name, iban, created_at, is_blacklisted, country, avg_amount, count)
        ("Acme Supplies Ltd.", "CH93 0076 2011 6238 5295 7", "2020-03-15", 0, "CH", 1250.0, 42),
        ("Global Parts SA", "CH56 0483 5012 3456 7890 1", "2019-07-22", 0, "CH", 3400.0, 87),
        ("TechVision GmbH", "DE89 3704 0044 0532 0130 00", "2021-11-05", 0, "DE", 8200.0, 23),
        ("SwissLogistics AG", "CH12 0024 3243 1234 5678 9", "2018-01-10", 0, "CH", 15000.0, 156),
        # Fournisseur suspect : créé récemment
        ("FastSupply Ltd.", "CH99 9999 9999 9999 9999 9", "2026-09-28", 0, "CH", 0.0, 0),
        # Fournisseur blacklisté
        ("ShadowTrade Inc.", "CY12 3456 7890 1234 5678 9012", "2026-06-01", 1, "CY", 8500.0, 3),
    ]
    cur.executemany(
        "INSERT OR IGNORE INTO suppliers (name, iban, created_at, is_blacklisted, country, avg_invoice_amount, invoice_count) VALUES (?, ?, ?, ?, ?, ?, ?)",
        suppliers,
    )

    # --- Bons de commande ---
    pos = [
        ("PO-2026-0117", "Acme Supplies Ltd.", 1250.0, 250.0, "5x Widget A, 2x Widget B", "2026-09-15"),
        ("PO-2026-0200", "Global Parts SA", 3400.0, 680.0, "10x Gear X", "2026-09-20"),
        ("PO-2026-0300", "TechVision GmbH", 8200.0, 1640.0, "Server rack + config", "2026-09-22"),
        ("PO-2026-0400", "SwissLogistics AG", 15000.0, 3000.0, "Annual transport contract", "2026-09-25"),
    ]
    cur.executemany(
        "INSERT OR IGNORE INTO purchase_orders (po_reference, supplier_name, amount, vat, items, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        pos,
    )

    # --- Historique factures (pour détecter les doublons) ---
    history = [
        # Acme Supplies : factures régulières
        ("INV-2026-0010", "Acme Supplies Ltd.", 1180.0, 236.0, 20.0, "PO-2026-0100", "CH93 0076 2011 6238 5295 7", "2026-06-10", "approved"),
        ("INV-2026-0025", "Acme Supplies Ltd.", 1320.0, 264.0, 20.0, "PO-2026-0110", "CH93 0076 2011 6238 5295 7", "2026-07-15", "approved"),
        ("INV-2026-0038", "Acme Supplies Ltd.", 1250.0, 250.0, 20.0, "PO-2026-0115", "CH93 0076 2011 6238 5295 7", "2026-08-20", "approved"),
        # ⚠️ Doublon potentiel de INV-2026-0042 (même montant Acme)
        ("INV-2026-0040", "Acme Supplies Ltd.", 1250.0, 250.0, 20.0, "PO-2026-0116", "CH93 0076 2011 6238 5295 7", "2026-09-01", "approved"),
        # TechVision : plusieurs factures
        ("INV-2026-0030", "TechVision GmbH", 7900.0, 1580.0, 20.0, "PO-2026-0250", "DE89 3704 0044 0532 0130 00", "2026-07-25", "approved"),
        ("INV-2026-0045", "TechVision GmbH", 8350.0, 1670.0, 20.0, "PO-2026-0280", "DE89 3704 0044 0532 0130 00", "2026-09-05", "approved"),
    ]
    cur.executemany(
        "INSERT OR IGNORE INTO invoices_history (invoice_id, supplier_name, amount, vat, vat_rate, po_reference, iban, issued_at, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        history,
    )

    conn.commit()
    conn.close()
    print(f"[OK] Seeded {len(suppliers)} suppliers, {len(pos)} POs, {len(history)} history invoices")


def reset_db() -> None:
    """Drop all tables and recreate them. USE WITH CAUTION."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS suppliers")
    cur.execute("DROP TABLE IF EXISTS invoices_history")
    cur.execute("DROP TABLE IF EXISTS purchase_orders")
    conn.commit()
    conn.close()
    init_db()
    seed_data()


if __name__ == "__main__":
    init_db()
    seed_data()
    print(f"\n[OK] Database ready at: {DB_PATH}")