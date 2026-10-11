"""Unit tests for the PDF report generator."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.pdf_report import generate_report_pdf


def _sample_analysis():
    return {
        "id": "test-001",
        "document_type": "invoice",
        "document_reference": "INV-2026-0042",
        "supplier_name": "Acme Supplies Ltd.",
        "amount": 1250.0,
        "currency": "USD",
        "vat": 250.0,
        "po_reference": "PO-2026-0117",
        "risk_score": 30,
        "risk_level": "medium",
        "decision": "alerted",
        "fraud_json": '{"anomalies": [{"severity": "high", "message": "Possible duplicate"}]}',
    }


def test_pdf_generation_returns_bytes():
    pdf = generate_report_pdf(_sample_analysis())
    assert isinstance(pdf, bytes)
    assert len(pdf) > 1000  # PDF should be at least 1 KB


def test_pdf_starts_with_magic_header():
    pdf = generate_report_pdf(_sample_analysis())
    assert pdf[:4] == b"%PDF", "PDF should start with %PDF magic header"


def test_pdf_with_empty_analysis():
    pdf = generate_report_pdf({"id": "empty"})
    assert isinstance(pdf, bytes)
    assert len(pdf) > 500


def test_pdf_critical_level():
    analysis = _sample_analysis()
    analysis["risk_level"] = "critical"
    analysis["risk_score"] = 90
    analysis["decision"] = "escalated"
    pdf = generate_report_pdf(analysis)
    assert pdf[:4] == b"%PDF"