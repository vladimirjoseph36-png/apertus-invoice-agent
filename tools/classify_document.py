"""
Document classifier - hybrid approach.

1. Fast heuristic rules (keywords, patterns)
2. LLM fallback via Groq if rules are ambiguous

Author: Anio Joseph
Project: Hack Apertus - October 2026
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict

from dotenv import load_dotenv

load_dotenv()

from groq import Groq


INVOICE_KEYWORDS = [
    r"\binvoice\b", r"\bfacture\b", r"\brechnung\b", r"\bfattura\b",
    r"INV-\d{4}-\d{4}", r"\bbill\b", r"\btax invoice\b",
]

PO_KEYWORDS = [
    r"\bpurchase order\b", r"\bbon de commande\b", r"\bbestellung\b",
    r"\bordine\b", r"PO-\d{4}-\d{4}",
]

UNKNOWN_HINTS = [
    r"\bquote\b", r"\bdevis\b", r"\bcredit note\b", r"\bavoir\b",
    r"\bbank statement\b",
]


def _rule_based_classify(text: str) -> Dict[str, Any]:
    text_lower = text.lower()
    invoice_hits = sum(1 for p in INVOICE_KEYWORDS if re.search(p, text_lower, re.IGNORECASE))
    po_hits = sum(1 for p in PO_KEYWORDS if re.search(p, text_lower, re.IGNORECASE))
    unknown_hits = sum(1 for p in UNKNOWN_HINTS if re.search(p, text_lower, re.IGNORECASE))

    if invoice_hits >= 1 and invoice_hits > po_hits:
        return {
            "document_type": "invoice",
            "confidence": min(0.7 + invoice_hits * 0.1, 0.95),
            "method": "rules",
            "details": {"invoice_hits": invoice_hits, "po_hits": po_hits},
        }

    if po_hits >= 1 and po_hits > invoice_hits:
        return {
            "document_type": "purchase_order",
            "confidence": min(0.7 + po_hits * 0.1, 0.95),
            "method": "rules",
            "details": {"invoice_hits": invoice_hits, "po_hits": po_hits},
        }

    return {
        "document_type": "unknown",
        "confidence": 0.3,
        "method": "rules",
        "details": {
            "invoice_hits": invoice_hits,
            "po_hits": po_hits,
            "unknown_hits": unknown_hits,
        },
    }


def _llm_based_classify(text: str) -> Dict[str, Any]:
    api_key = os.getenv("GROQ_API_KEY", "")
    model = os.getenv("APERTUS_MODEL", "openai/gpt-oss-120b")

    if not api_key:
        return {
            "document_type": "unknown",
            "confidence": 0.0,
            "method": "llm",
            "details": {"error": "GROQ_API_KEY not set"},
        }

    client = Groq(api_key=api_key)

    prompt = (
        "Classify this financial document. Respond ONLY with one word among:\n"
        "- invoice\n- purchase_order\n- unknown\n\n"
        "Document:\n\"\"\"\n" + text[:2000] + "\n\"\"\"\n\nYour answer (one word):"
    )

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=10,
            temperature=0.0,
        )
        answer = (response.choices[0].message.content or "").strip().lower()

        if "invoice" in answer:
            doc_type = "invoice"
        elif "purchase" in answer or answer == "po" or "order" in answer:
            doc_type = "purchase_order"
        else:
            doc_type = "unknown"

        return {
            "document_type": doc_type,
            "confidence": 0.85,
            "method": "llm",
            "details": {"raw_answer": answer},
        }
    except Exception as e:
        return {
            "document_type": "unknown",
            "confidence": 0.0,
            "method": "llm",
            "details": {"error": str(e)},
        }


def classify_document(document_text: str) -> Dict[str, Any]:
    """
    Classify a financial document (hybrid rules + LLM).
    """
    if not document_text or not document_text.strip():
        return {
            "document_type": "unknown",
            "confidence": 1.0,
            "method": "rules",
            "details": {"reason": "empty input"},
        }

    rule_result = _rule_based_classify(document_text)

    if rule_result["confidence"] >= 0.8:
        return rule_result

    llm_result = _llm_based_classify(document_text)

    if llm_result["confidence"] > rule_result["confidence"]:
        return llm_result

    return rule_result


if __name__ == "__main__":
    tests = [
        ("Invoice #INV-2026-0042 Supplier: Acme Amount: 1250", "invoice"),
        ("Purchase Order PO-2026-0117 Supplier: Acme Amount: 1250", "purchase_order"),
        ("Bon de commande PO-2026-0200 Fournisseur: Global Parts", "purchase_order"),
        ("Facture INV-2026-0010 Total: 500", "invoice"),
        ("Some random text without keywords", "unknown"),
    ]

    for text, expected in tests:
        result = classify_document(text)
        status = "OK" if result["document_type"] == expected else "MISMATCH"
        print(f"[{status}] '{text[:40]}...' -> {result['document_type']} ({result['confidence']:.2f}, {result['method']})")