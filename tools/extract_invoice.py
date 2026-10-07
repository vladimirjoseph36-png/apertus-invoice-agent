"""
Tool: extract_invoice

Extracts structured data from a supplier invoice (text or PDF).
Author: Anio Joseph
Project: Hack Apertus - October 2026
"""

import re
from typing import Any


def extract_invoice(invoice_text: str) -> dict[str, Any]:
    """Extract structured data from an invoice text."""
    invoice_id = _search(r"Invoice\s*#\s*([A-Z0-9\-]+)", invoice_text)
    supplier = _search(r"Supplier:\s*(.+)", invoice_text)
    po_ref = _search(r"PO\s*Reference:\s*([A-Z0-9\-]+)", invoice_text)
    amount = _search_amount(r"Amount:\s*\$?([\d,]+\.\d{2})", invoice_text)
    vat = _search_amount(r"VAT:\s*\$?([\d,]+\.\d{2})", invoice_text)

    return {
        "invoice_id": invoice_id or "UNKNOWN",
        "supplier": supplier or "UNKNOWN",
        "po_reference": po_ref or "UNKNOWN",
        "amount": amount or 0.0,
        "vat": vat or 0.0,
        "raw": invoice_text,
    }


def _search(pattern: str, text: str) -> str | None:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    return match.group(1).strip() if match else None


def _search_amount(pattern: str, text: str) -> float | None:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return None
    return float(match.group(1).replace(",", ""))
