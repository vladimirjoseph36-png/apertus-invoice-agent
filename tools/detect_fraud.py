"""
Fraud detection engine for invoice reconciliation.

Combines multiple techniques:
1. Heuristic rules (11+ signals)
2. Statistical analysis (z-score on supplier amounts)
3. Machine learning (Isolation Forest from scikit-learn)
4. Historical data lookup (SQLite)

Output:
{
    "risk_score": 0-100,
    "risk_level": "low|medium|high|critical",
    "anomalies": [...],
    "recommendation": "...",
    "details": {...}
}

Author: Anio Joseph
Project: Hack Apertus - October 2026
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

try:
    from sklearn.ensemble import IsolationForest
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    print("[WARNING] scikit-learn not installed. ML features disabled.")


DB_PATH = Path(__file__).resolve().parent.parent / "data" / "invoices.db"

# Seuils configurables
APPROVAL_THRESHOLD = 10000.0       # Seuil d'approbation manuelle
RECENT_SUPPLIER_DAYS = 90          # Fournisseur "récent" si < 90 jours
DUPLICATE_TOLERANCE_PCT = 0.02     # 2% de tolérance pour doublons
AMOUNT_ROUND_THRESHOLD = 1000.0    # Montants > 1000 = suspect si rond
VAT_RATE_STANDARD = 0.20           # 20% TVA standard CH
VAT_RATE_TOLERANCE = 0.03          # ±3% accepté


# ----------------------------------------------------------------------
# Règles heuristiques
# ----------------------------------------------------------------------

def _check_approval_threshold(amount: float) -> Optional[Dict[str, Any]]:
    """Détecte les montants juste sous le seuil d'approbation."""
    if amount >= APPROVAL_THRESHOLD:
        return None
    if amount >= APPROVAL_THRESHOLD * 0.95:
        return {
            "code": "JUST_UNDER_APPROVAL_THRESHOLD",
            "severity": "medium",
            "weight": 15,
            "message": f"Montant {amount:.2f} CHF juste sous le seuil d'approbation ({APPROVAL_THRESHOLD:.0f} CHF).",
            "details": {"amount": amount, "threshold": APPROVAL_THRESHOLD},
        }
    return None


def _check_recent_supplier(supplier_name: str) -> Optional[Dict[str, Any]]:
    """Détecte un fournisseur créé récemment."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT created_at, is_blacklisted FROM suppliers WHERE name = ?", (supplier_name,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return {
            "code": "UNKNOWN_SUPPLIER",
            "severity": "high",
            "weight": 20,
            "message": f"Fournisseur '{supplier_name}' inconnu de la base.",
            "details": {},
        }

    created_at = datetime.strptime(row["created_at"], "%Y-%m-%d")
    days_old = (datetime.now() - created_at).days

    if days_old < RECENT_SUPPLIER_DAYS:
        return {
            "code": "RECENT_SUPPLIER",
            "severity": "high",
            "weight": 25,
            "message": f"Fournisseur créé il y a seulement {days_old} jours.",
            "details": {"created_at": row["created_at"], "days_old": days_old},
        }
    return None


def _check_blacklist(supplier_name: str) -> Optional[Dict[str, Any]]:
    """Détecte un fournisseur blacklisté."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT is_blacklisted FROM suppliers WHERE name = ?", (supplier_name,))
    row = cur.fetchone()
    conn.close()

    if row and row["is_blacklisted"]:
        return {
            "code": "BLACKLISTED_SUPPLIER",
            "severity": "critical",
            "weight": 50,
            "message": f"⚠️ Fournisseur '{supplier_name}' présent sur la liste de surveillance.",
            "details": {},
        }
    return None


def _check_iban_mismatch(supplier_name: str, invoice_iban: Optional[str]) -> Optional[Dict[str, Any]]:
    """Détecte un changement d'IBAN."""
    if not invoice_iban:
        return None
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT iban FROM suppliers WHERE name = ?", (supplier_name,))
    row = cur.fetchone()
    conn.close()

    if row and row["iban"] and row["iban"] != invoice_iban:
        return {
            "code": "IBAN_MISMATCH",
            "severity": "critical",
            "weight": 40,
            "message": f"IBAN différent de l'historique fournisseur ({row['iban']} vs {invoice_iban}).",
            "details": {"expected": row["iban"], "provided": invoice_iban},
        }
    return None


def _check_duplicate(invoice_id: str, supplier_name: str, amount: float) -> Optional[Dict[str, Any]]:
    """Détecte un doublon de facture (même fournisseur, même montant, récemment)."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    # Doublons sur les 90 derniers jours
    threshold_date = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
    cur.execute("""
        SELECT invoice_id, amount, issued_at FROM invoices_history
        WHERE supplier_name = ? AND issued_at >= ? AND invoice_id != ?
    """, (supplier_name, threshold_date, invoice_id))
    rows = cur.fetchall()
    conn.close()

    for row in rows:
        if abs(row["amount"] - amount) / max(row["amount"], 1) <= DUPLICATE_TOLERANCE_PCT:
            return {
                "code": "POSSIBLE_DUPLICATE",
                "severity": "high",
                "weight": 30,
                "message": f"Doublon possible avec la facture {row['invoice_id']} (même fournisseur, montant similaire).",
                "details": {"duplicate_invoice": row["invoice_id"], "duplicate_amount": row["amount"]},
            }
    return None


def _check_vat_rate(amount: float, vat: float) -> Optional[Dict[str, Any]]:
    """Vérifie que le taux de TVA est cohérent."""
    if amount <= 0:
        return None
    vat_rate = vat / amount
    if abs(vat_rate - VAT_RATE_STANDARD) > VAT_RATE_TOLERANCE:
        return {
            "code": "ANOMALOUS_VAT_RATE",
            "severity": "medium",
            "weight": 15,
            "message": f"Taux de TVA inhabituel : {vat_rate*100:.1f}% (attendu ~{VAT_RATE_STANDARD*100:.0f}%).",
            "details": {"vat_rate": vat_rate, "expected": VAT_RATE_STANDARD},
        }
    return None


def _check_round_amount(amount: float) -> Optional[Dict[str, Any]]:
    """Détecte les montants ronds suspects (pas d'unités)."""
    if amount >= AMOUNT_ROUND_THRESHOLD and amount % 100 == 0:
        return {
            "code": "ROUND_AMOUNT",
            "severity": "low",
            "weight": 5,
            "message": f"Montant rond suspect : {amount:.2f} CHF (aucune unité).",
            "details": {"amount": amount},
        }
    return None


def _check_missing_po(po_reference: Optional[str]) -> Optional[Dict[str, Any]]:
    """Détecte l'absence de bon de commande."""
    if not po_reference:
        return {
            "code": "MISSING_PO",
            "severity": "medium",
            "weight": 20,
            "message": "Aucun bon de commande associé à cette facture.",
            "details": {},
        }
    return None


# ----------------------------------------------------------------------
# Analyse statistique (z-score)
# ----------------------------------------------------------------------

def _check_zscore(supplier_name: str, amount: float) -> Optional[Dict[str, Any]]:
    """Détecte un montant aberrant par rapport à l'historique du fournisseur."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT amount FROM invoices_history WHERE supplier_name = ?", (supplier_name,))
    rows = cur.fetchall()
    conn.close()

    amounts = [r["amount"] for r in rows]
    if len(amounts) < 3:
        return None  # pas assez de données

    mean = float(np.mean(amounts))
    std = float(np.std(amounts))
    if std == 0:
        return None

    z = (amount - mean) / std
    if abs(z) > 2.5:
        return {
            "code": "STATISTICAL_OUTLIER",
            "severity": "medium",
            "weight": 15,
            "message": f"Montant statistiquement aberrant (z-score = {z:.2f}). Moyenne historique : {mean:.2f} CHF.",
            "details": {"z_score": z, "mean": mean, "std": std, "amount": amount},
        }
    return None


# ----------------------------------------------------------------------
# Machine Learning : Isolation Forest
# ----------------------------------------------------------------------

def _check_isolation_forest(supplier_name: str, amount: float, vat: float) -> Optional[Dict[str, Any]]:
    """Détecte les anomalies via Isolation Forest (non supervisé)."""
    if not SKLEARN_AVAILABLE:
        return None

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT amount, vat FROM invoices_history")
    rows = cur.fetchall()
    conn.close()

    if len(rows) < 5:
        return None

    X = np.array([[r["amount"], r["vat"]] for r in rows])
    model = IsolationForest(contamination=0.1, random_state=42)
    model.fit(X)

    new_point = np.array([[amount, vat]])
    prediction = model.predict(new_point)[0]  # -1 = anomalie, 1 = normal
    score = model.decision_function(new_point)[0]  # plus négatif = plus anormal

    if prediction == -1:
        return {
            "code": "ML_ANOMALY",
            "severity": "medium",
            "weight": 15,
            "message": f"Anomalie détectée par Isolation Forest (score = {score:.3f}).",
            "details": {"ml_score": float(score)},
        }
    return None


# ----------------------------------------------------------------------
# Moteur principal
# ----------------------------------------------------------------------

def detect_fraud(
    invoice_id: str,
    supplier_name: str,
    amount: float,
    vat: float,
    po_reference: Optional[str] = None,
    iban: Optional[str] = None,
    issued_at: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Analyse complète de fraude sur une facture.

    Returns:
        {
            "risk_score": 0-100,
            "risk_level": "low|medium|high|critical",
            "anomalies": [list of anomaly dicts],
            "recommendation": str,
            "details": dict,
        }
    """
    anomalies: List[Dict[str, Any]] = []

    # --- Règles heuristiques ---
    for check in [
        _check_blacklist(supplier_name),
        _check_approval_threshold(amount),
        _check_recent_supplier(supplier_name),
        _check_iban_mismatch(supplier_name, iban),
        _check_duplicate(invoice_id, supplier_name, amount),
        _check_vat_rate(amount, vat),
        _check_round_amount(amount),
        _check_missing_po(po_reference),
    ]:
        if check:
            anomalies.append(check)

    # --- Analyse statistique ---
    zscore = _check_zscore(supplier_name, amount)
    if zscore:
        anomalies.append(zscore)

    # --- Machine Learning ---
    ml = _check_isolation_forest(supplier_name, amount, vat)
    if ml:
        anomalies.append(ml)

    # --- Score global (plafonné à 100) ---
    total_weight = sum(a["weight"] for a in anomalies)
    risk_score = min(total_weight, 100)

    # --- Niveau de risque ---
    if risk_score >= 70:
        risk_level = "critical"
    elif risk_score >= 40:
        risk_level = "high"
    elif risk_score >= 20:
        risk_level = "medium"
    else:
        risk_level = "low"

    # --- Recommandation ---
    if risk_level == "critical":
        recommendation = "🚨 ESCALADE MANUELLE REQUISE — Ne pas approuver. Vérifier immédiatement."
    elif risk_level == "high":
        recommendation = "⚠️ Vérification manuelle recommandée avant approbation."
    elif risk_level == "medium":
        recommendation = "🟡 Quelques signaux à surveiller. Vérifier les points listés."
    else:
        recommendation = "✅ Aucun signal de fraude significatif. Approbation possible."

    return {
        "risk_score": risk_score,
        "risk_level": risk_level,
        "anomalies": anomalies,
        "anomaly_count": len(anomalies),
        "recommendation": recommendation,
        "details": {
            "invoice_id": invoice_id,
            "supplier_name": supplier_name,
            "amount": amount,
            "vat": vat,
            "ml_enabled": SKLEARN_AVAILABLE,
        },
    }


if __name__ == "__main__":
    # Test rapide
    print("=== Test 1: Facture normale ===")
    result = detect_fraud(
        invoice_id="INV-2026-0042",
        supplier_name="Acme Supplies Ltd.",
        amount=1250.0,
        vat=250.0,
        po_reference="PO-2026-0117",
        iban="CH93 0076 2011 6238 5295 7",
    )
    print(f"Score: {result['risk_score']} - Niveau: {result['risk_level']}")
    print(f"Anomalies: {len(result['anomalies'])}")
    print(f"Recommandation: {result['recommendation']}")

    print("\n=== Test 2: Facture frauduleuse ===")
    result = detect_fraud(
        invoice_id="INV-2026-FRAUD",
        supplier_name="FastSupply Ltd.",
        amount=9950.0,
        vat=1990.0,
        po_reference=None,
        iban="CH99 9999 9999 9999 9999 9",
    )
    print(f"Score: {result['risk_score']} - Niveau: {result['risk_level']}")
    for a in result["anomalies"]:
        print(f"  [{a['severity']}] {a['message']}")
    print(f"Recommandation: {result['recommendation']}")