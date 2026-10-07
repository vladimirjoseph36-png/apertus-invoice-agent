"""
Tool: find_purchase_order
Author: Anio Joseph
"""

from typing import Any

_PO_DATABASE: dict[str, dict[str, Any]] = {
    "PO-2026-0117": {
        "po_reference": "PO-2026-0117",
        "supplier": "Acme Supplies Ltd.",
        "amount": 1250.00,
        "vat": 250.00,
        "items": ["5x Widget A", "2x Widget B"],
        "status": "OPEN",
    },
    "PO-2026-0118": {
        "po_reference": "PO-2026-0118",
        "supplier": "Beta Components Inc.",
        "amount": 890.00,
        "vat": 178.00,
        "items": ["10x Bolt M8"],
        "status": "OPEN",
    },
}


def find_purchase_order(po_reference: str) -> dict[str, Any]:
    """Find a purchase order by its reference."""
    po = _PO_DATABASE.get(po_reference)
    if not po:
        return {"found": False, "po_reference": po_reference}
    return {"found": True, **po}
