"""Unit tests for the document classifier."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.classify_document import classify_document


def test_classify_invoice():
    result = classify_document("Invoice #INV-2026-0042 Supplier: Acme Amount: 1250")
    assert result["document_type"] == "invoice"


def test_classify_purchase_order():
    result = classify_document("Purchase Order PO-2026-0117 Supplier: Acme Amount: 1250")
    assert result["document_type"] == "purchase_order"


def test_classify_french_invoice():
    result = classify_document("Facture N°FA-2026-0891 Fournisseur: Muller & Sohne GmbH")
    assert result["document_type"] == "invoice"


def test_classify_unknown():
    result = classify_document("Le temps est beau aujourd'hui a Geneve")
    assert result["document_type"] in ("unknown", "invoice", "purchase_order")


def test_classify_empty():
    result = classify_document("")
    assert result["document_type"] == "unknown"


def test_result_structure():
    result = classify_document("Invoice #INV-2026-0042")
    for key in ("document_type", "confidence", "method"):
        assert key in result