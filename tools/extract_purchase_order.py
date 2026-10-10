"""
Extract structured data from a purchase order (PO) text.

Uses regex-based extraction (no LLM call needed) for speed and reliability.

Author: Anio Joseph
Project: Hack Apertus - October 2026
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional


def _extract_po_reference(text: str) -> Optional[str]:
    """Find PO reference like PO-2026-0117 or P.O. 2026-0117."""
    patterns = [
        r"PO-\d{4}-\d{4}",
        r"P\.O\.\s*\d{4}-\d{4}",
        r"PO\s*#?\s*\d{4}-\d{4}",
        r"bon de commande\s*n[°o]?\s*(PO-\d{4}-\d{4})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            ref = match.group(0)
            # Normalize
            ref = re.sub(r"[^\d-]", "", ref)
            if not ref.startswith("PO-"):
                ref = "PO-" + ref.lstrip("-")
            return ref
    return None


def _extract_supplier(text: str) -> Optional[str]:
    """Find supplier name."""
    patterns = [
        r"Supplier\s*[:\-]\s*(.+)",
        r"Fournisseur\s*[:\-]\s*(.+)",
        r"Vendor\s*[:\-]\s*(.+)",
        r"From\s*[:\-]\s*(.+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            line = match.group(1).strip().split("\n")[0]
            # Remove trailing PO/Amount
            line = re.split(r"\s+(PO|Amount|VAT|Total)", line, flags=re.IGNORECASE)[0]
            return line.strip()
    return None


def _extract_amount(text: str) -> Optional[float]:
    """Find amount like $1,250.00 or 1250.00 CHF."""
    patterns = [
        r"(?:Amount|Total|Montant|Total amount)\s*[:\-]?\s*[\$€]?\s*([\d,]+(?:\.\d{1,2})?)",
        r"[\$€]\s*([\d,]+(?:\.\d{1,2})?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            raw = match.group(1).replace(",", "")
            try:
                return float(raw)
            except ValueError:
                continue
    return None


def _extract_vat(text: str) -> Optional[float]:
    """Find VAT amount like $250.00 or VAT: 250."""
    patterns = [
        r"VAT\s*[:\-]?\s*[\$€]?\s*([\d,]+(?:\.\d{1,2})?)",
        r"TVA\s*[:\-]?\s*[\$€]?\s*([\d,]+(?:\.\d{1,2})?)",
        r"Tax\s*[:\-]?\s*[\$€]?\s*([\d,]+(?:\.\d{1,2})?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            raw = match.group(1).replace(",", "")
            try:
                return float(raw)
            except ValueError:
                continue
    return None


def _extract_items(text: str) -> Optional[str]:
    """Find items list."""
    patterns = [
        r"Items?\s*[:\-]\s*(.+)",
        r"Articles?\s*[:\-]\s*(.+)",
        r"Description\s*[:\-]\s*(.+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            line = match.group(1).strip().split("\n")[0]
            return line
    return None


def extract_purchase_order(po_text: str) -> Dict[str, Any]:
    """
    Extract structured data from a purchase order text.

    Args:
        po_text: The raw text of the purchase order.

    Returns:
        {
            "po_reference": str or None,
            "supplier_name": str or None,
            "amount": float or None,
            "vat": float or None,
            "items": str or None,
            "success": bool,
            "missing_fields": [list of missing field names]
        }
    """
    po_reference = _extract_po_reference(po_text)
    supplier_name = _extract_supplier(po_text)
    amount = _extract_amount(po_text)
    vat = _extract_vat(po_text)
    items = _extract_items(po_text)

    missing_fields = []
    if not po_reference:
        missing_fields.append("po_reference")
    if not supplier_name:
        missing_fields.append("supplier_name")
    if amount is None:
        missing_fields.append("amount")
    if vat is None:
        missing_fields.append("vat")

    return {
        "po_reference": po_reference,
        "supplier_name": supplier_name,
        "amount": amount,
        "vat": vat,
        "items": items,
        "success": len(missing_fields) == 0,
        "missing_fields": missing_fields,
    }


if __name__ == "__main__":
    tests = [
        "Purchase Order PO-2026-0117\nSupplier: Acme Supplies Ltd.\nAmount: $1,250.00\nVAT: $250.00\nItems: 5x Widget A",
        "Bon de commande PO-2026-0200\nFournisseur: Global Parts SA\nAmount: 3,400.00\nTVA: 680.00",
        "PO-2026-0300 Vendor: TechVision GmbH Total: 8200.00",
    ]
    for text in tests:
        result = extract_purchase_order(text)
        print(f"--- {text[:40]}... ---")
        for key, value in result.items():
            print(f"  {key}: {value}")
        print()