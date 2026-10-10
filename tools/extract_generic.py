"""
Generic LLM-based extraction for any financial document.

Instead of fragile regex patterns, this uses the LLM to extract
whatever fields are present in the document, regardless of format.

Returns a flexible JSON with all detected fields.

Author: Anio Joseph
Project: Hack Apertus - October 2026
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict

from dotenv import load_dotenv

load_dotenv()

from groq import Groq


EXTRACTION_PROMPT = """You are a financial document data extraction engine.

Analyze the document below and extract ALL relevant fields you can find.

Return ONLY a valid JSON object (no markdown, no code block, no explanation) with this structure:

{
  "document_type": "invoice" | "purchase_order" | "credit_note" | "quote" | "bank_statement" | "unknown",
  "document_reference": "<invoice number, PO number, or document ID>",
  "supplier_name": "<supplier or vendor name, or null>",
  "customer_name": "<customer or buyer name, or null>",
  "amount": <total amount as number, or null>,
  "currency": "<3-letter code like CHF, EUR, USD, or null>",
  "vat": <VAT amount as number, or null>,
  "vat_rate": <VAT rate as number (e.g. 0.20), or null>,
  "issue_date": "<YYYY-MM-DD or null>",
  "due_date": "<YYYY-MM-DD or null>",
  "po_reference": "<purchase order reference, or null>",
  "iban": "<IBAN if present, or null>",
  "items": "<description of items, or null>",
  "raw_notes": "<any other relevant info you see, or null>"
}

RULES:
- If a field is not present, use null.
- Be precise with numbers: remove thousand separators, use dot as decimal.
- Detect currency from symbols: dollar = USD, euro = EUR, CHF = CHF, pound = GBP.
- If the document is clearly NOT a financial document, set document_type to "unknown".
- Do NOT invent values.

DOCUMENT:
\"\"\"
__DOCUMENT_PLACEHOLDER__
\"\"\"

JSON response:"""


def _clean_json_response(raw: str) -> str:
    """Remove markdown code blocks and other noise from LLM response."""
    text = raw.strip()
    # Remove ```json ... ``` wrappers
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    # Find first { and last }
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start:end + 1]
    return text


def _normalize_field(value: Any) -> Any:
    """Normalize null-like strings."""
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned.lower() in ("null", "none", "n/a", "na", "", "unknown", "-"):
            return None
        return cleaned
    return value


def extract_generic(document_text: str) -> Dict[str, Any]:
    """
    Extract structured data from ANY financial document using the LLM.

    Args:
        document_text: The full text of the document.

    Returns:
        {
            "success": bool,
            "document_type": str,
            "fields": {...},
            "error": str or None
        }
    """
    api_key = os.getenv("GROQ_API_KEY", "")
    model = os.getenv("APERTUS_MODEL", "openai/gpt-oss-120b")

    if not api_key:
        return {
            "success": False,
            "document_type": "unknown",
            "fields": {},
            "error": "GROQ_API_KEY not set",
        }

    if not document_text or not document_text.strip():
        return {
            "success": False,
            "document_type": "unknown",
            "fields": {},
            "error": "empty document",
        }

    client = Groq(api_key=api_key)

    try:
        prompt = EXTRACTION_PROMPT.replace("__DOCUMENT_PLACEHOLDER__", document_text[:6000])

        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800,
            temperature=0.0,
        )
        raw = response.choices[0].message.content or ""
        cleaned = _clean_json_response(raw)

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            return {
                "success": False,
                "document_type": "unknown",
                "fields": {},
                "error": f"JSON parse error: {e}",
                "raw_response": raw[:500],
            }

        # Normalize
        normalized = {k: _normalize_field(v) for k, v in data.items()}

        doc_type = normalized.get("document_type") or "unknown"
        fields = {k: v for k, v in normalized.items() if k != "document_type"}

        return {
            "success": True,
            "document_type": doc_type,
            "fields": fields,
            "error": None,
        }

    except Exception as e:
        return {
            "success": False,
            "document_type": "unknown",
            "fields": {},
            "error": f"{type(e).__name__}: {e}",
        }


if __name__ == "__main__":
    tests = [
        # Test 1 : facture en francais, format non standard
        """Cher client,
        Veuillez trouver ci-joint notre facture n F-2026-0891 emise le 15/03/2026
        pour un montant total de 4.567,89 EUR (TVA 913,58 EUR) concernant la
        commande CMD-2026-042. Fournisseur : Muller & Sohne GmbH,
        IBAN : DE89 3704 0044 0532 0130 00.""",

        # Test 2 : PO en anglais
        """PURCHASE ORDER
        PO Number: PO-2026-0117
        Date: 2026-09-15
        Vendor: Acme Supplies Ltd.
        Total: 1250.00
        VAT: 250.00 (20%)
        Items: 5x Widget A, 2x Widget B""",

        # Test 3 : document non financier
        """Le temps est beau aujourd'hui a Geneve. La temperature est de 22 degres.""",
    ]

    for i, text in enumerate(tests, 1):
        print(f"\n=== Test {i} ===")
        result = extract_generic(text)
        print(f"Success: {result['success']}")
        print(f"Type: {result['document_type']}")
        if result['success']:
            for k, v in result['fields'].items():
                if v is not None:
                    print(f"  {k}: {v}")
        else:
            print(f"Error: {result['error']}")