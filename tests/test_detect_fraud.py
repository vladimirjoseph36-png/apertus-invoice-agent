"""
Unit tests for the fraud detection engine.

Run with: pytest tests/test_detect_fraud.py -v
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.detect_fraud import detect_fraud


def test_normal_invoice_low_risk():
    """A regular invoice from a known supplier should have low risk."""
    result = detect_fraud(
        invoice_id="INV-TEST-NORMAL",
        supplier_name="Acme Supplies Ltd.",
        amount=1250.0,
        vat=250.0,
        po_reference="PO-2026-0117",
        iban="CH93 0076 2011 6238 5295 7",
    )
    assert result["risk_level"] in ("low", "medium")
    assert result["risk_score"] >= 0
    assert "recommendation" in result


def test_fraudulent_invoice_high_risk():
    """The demo fraud invoice should be flagged as high/critical."""
    result = detect_fraud(
        invoice_id="INV-TEST-FRAUD",
        supplier_name="FastSupply Ltd.",
        amount=9950.0,
        vat=1990.0,
        po_reference=None,
        iban="CH99 9999 9999 9999 9999 9",
    )
    assert result["risk_score"] >= 40
    assert result["risk_level"] in ("high", "critical")
    assert result["anomaly_count"] >= 1


def test_amount_just_under_threshold_is_flagged():
    """An amount just below the approval threshold should raise a flag."""
    result = detect_fraud(
        invoice_id="INV-TEST-THRESHOLD",
        supplier_name="Acme Supplies Ltd.",
        amount=9950.0,
        vat=1990.0,
        po_reference="PO-2026-0117",
    )
    codes = [a["code"] for a in result["anomalies"]]
    assert "JUST_UNDER_APPROVAL_THRESHOLD" in codes


def test_unknown_supplier_is_flagged():
    """An unknown supplier should be flagged."""
    result = detect_fraud(
        invoice_id="INV-TEST-UNKNOWN",
        supplier_name="Unknown Corp XYZ",
        amount=500.0,
        vat=100.0,
    )
    codes = [a["code"] for a in result["anomalies"]]
    assert "UNKNOWN_SUPPLIER" in codes


def test_result_structure():
    """The result should always contain the required keys."""
    result = detect_fraud(
        invoice_id="INV-TEST-STRUCT",
        supplier_name="Acme Supplies Ltd.",
        amount=1000.0,
        vat=200.0,
    )
    for key in ("risk_score", "risk_level", "anomalies", "recommendation", "details"):
        assert key in result, f"Missing key: {key}"