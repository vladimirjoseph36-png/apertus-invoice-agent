"""
Apertus Invoice Agent - Robust agent using Groq (OpenAI-compatible API).

Supports invoices AND purchase orders with universal LLM extraction.

Author: Anio Joseph
Project: Hack Apertus - October 2026
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Callable, Dict, List, Tuple

from dotenv import load_dotenv

load_dotenv()

from groq import Groq

from tools.extract_invoice import extract_invoice
from tools.find_purchase_order import find_purchase_order
from tools.compare_amounts import compare_amounts
from tools.send_alert import send_alert
from tools.mark_as_approved import mark_as_approved
from tools.detect_fraud import detect_fraud
from tools.classify_document import classify_document
from tools.extract_purchase_order import extract_purchase_order
from tools.extract_generic import extract_generic


TOOLS: Dict[str, Callable] = {
    "classify_document": classify_document,
    "extract_generic": extract_generic,
    "extract_invoice": extract_invoice,
    "extract_purchase_order": extract_purchase_order,
    "find_purchase_order": find_purchase_order,
    "compare_amounts": compare_amounts,
    "detect_fraud": detect_fraud,
    "send_alert": send_alert,
    "mark_as_approved": mark_as_approved,
}

# Schemas JSON pour le tool calling natif Groq
TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "extract_generic",
            "description": "UNIVERSAL EXTRACTION: extract ALL fields from ANY financial document (invoice, PO, quote) using the LLM. Returns document_type and a fields dict. ALWAYS call this FIRST.",
            "parameters": {
                "type": "object",
                "properties": {
                    "document_text": {"type": "string", "description": "The full text of the document."},
                },
                "required": ["document_text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "classify_document",
            "description": "Classify a financial document as 'invoice', 'purchase_order', or 'unknown'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "document_text": {"type": "string"},
                },
                "required": ["document_text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_purchase_order",
            "description": "Find a purchase order by its reference in the database.",
            "parameters": {
                "type": "object",
                "properties": {
                    "po_reference": {"type": "string"},
                },
                "required": ["po_reference"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_amounts",
            "description": "Compare invoice amounts/VAT against the purchase order.",
            "parameters": {
                "type": "object",
                "properties": {
                    "invoice_amount": {"type": "number"},
                    "invoice_vat": {"type": "number"},
                    "po_amount": {"type": "number"},
                    "po_vat": {"type": "number"},
                },
                "required": ["invoice_amount", "invoice_vat", "po_amount", "po_vat"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "detect_fraud",
            "description": "Analyze an invoice for fraud signals. Returns a risk score 0-100, level, and detailed anomalies. CALL THIS ON EVERY INVOICE.",
            "parameters": {
                "type": "object",
                "properties": {
                    "invoice_id": {"type": "string"},
                    "supplier_name": {"type": "string"},
                    "amount": {"type": "number"},
                    "vat": {"type": "number"},
                    "po_reference": {"type": ["string", "null"]},
                    "iban": {"type": ["string", "null"]},
                },
                "required": ["invoice_id", "supplier_name", "amount", "vat"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_alert",
            "description": "Send an alert when anomalies are detected.",
            "parameters": {
                "type": "object",
                "properties": {
                    "invoice_id": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["invoice_id", "reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mark_as_approved",
            "description": "Mark the invoice as approved when everything matches.",
            "parameters": {
                "type": "object",
                "properties": {
                    "invoice_id": {"type": "string"},
                },
                "required": ["invoice_id"],
            },
        },
    },
]

DEMO_INVOICES: Dict[str, str] = {
    "INV-2026-0042": """Invoice #INV-2026-0042
Supplier: Acme Supplies Ltd.
PO Reference: PO-2026-0117
Amount: $1,250.00
VAT: $250.00
Items: 5x Widget A, 2x Widget B
""",
    "INV-2026-FRAUD": """Invoice #INV-2026-FRAUD
Supplier: FastSupply Ltd.
PO Reference: NONE
Amount: $9,950.00
VAT: $1,990.00
Items: 3x Server rack, 2x Premium license
""",
}

DEMO_PURCHASE_ORDERS: Dict[str, str] = {
    "PO-2026-0117": """Purchase Order PO-2026-0117
Supplier: Acme Supplies Ltd.
Amount: $1,250.00
VAT: $250.00
Items: 5x Widget A, 2x Widget B
""",
    "PO-2026-0200": """Purchase Order PO-2026-0200
Supplier: Global Parts SA
Amount: $3,400.00
VAT: $680.00
Items: 10x Gear X
""",
    "PO-2026-0300": """Purchase Order PO-2026-0300
Supplier: TechVision GmbH
Amount: $8,200.00
VAT: $1,640.00
Items: Server rack + config
""",
    "PO-2026-0400": """Purchase Order PO-2026-0400
Supplier: SwissLogistics AG
Amount: $15,000.00
VAT: $3,000.00
Items: Annual transport contract
""",
}

OFF_TOPIC_KEYWORDS = [
    "blague", "joke", "chanson", "song", "poeme", "poem",
    "meteo", "weather", "recette", "recipe", "politique", "politics",
    "sport", "football", "film", "movie", "musique", "music",
    "raconte", "tell me", "explique-moi", "explain to me",
    "qui es-tu", "who are you",
]

INJECTION_KEYWORDS = [
    "ignore", "ignore previous", "oublie", "forget",
    "system prompt", "instruction", "you are now",
    "tu es maintenant", "pretend", "fais semblant",
    "jailbreak", "dan mode",
]


def _detect_demo_invoice(text: str) -> str | None:
    for invoice_id, full_text in DEMO_INVOICES.items():
        if invoice_id in text:
            has_details = (
                "Amount:" in text or "Supplier:" in text or "PO Reference:" in text
            )
            if not has_details:
                return full_text
    return None


def _detect_demo_po(text: str) -> str | None:
    for po_id, full_text in DEMO_PURCHASE_ORDERS.items():
        if po_id in text:
            has_details = ("Amount:" in text or "Supplier:" in text)
            if not has_details:
                return full_text
    return None


def _is_off_topic(text: str) -> bool:
    text_lower = text.lower()
    return any(kw in text_lower for kw in OFF_TOPIC_KEYWORDS)


def _is_injection_attempt(text: str) -> bool:
    text_lower = text.lower()
    return any(kw in text_lower for kw in INJECTION_KEYWORDS)


def _has_invoice_id(text: str) -> bool:
    return bool(re.search(r"INV-\d{4}-\d{4}", text, re.IGNORECASE))


def _has_po_reference(text: str) -> bool:
    return bool(re.search(r"PO-\d{4}-\d{4}", text, re.IGNORECASE))


def _has_amount(text: str) -> bool:
    return bool(re.search(r"\$?\d+(?:[.,]\d{1,2})?", text))


def _is_complete_invoice(text: str) -> Tuple[bool, List[str]]:
    missing = []
    if "Invoice" not in text and not _has_invoice_id(text):
        missing.append("Invoice ID")
    if "Supplier" not in text:
        missing.append("Supplier")
    if "PO Reference" not in text and "PO-" not in text:
        missing.append("PO Reference")
    if "Amount" not in text:
        missing.append("Amount")
    if "VAT" not in text:
        missing.append("VAT")
    return len(missing) == 0, missing


class ApertusInvoiceAgent:
    """Robust invoice reconciliation agent powered by Groq."""

    def __init__(self) -> None:
        self.model_id = os.getenv("APERTUS_MODEL", "openai/gpt-oss-120b")
        self.token = os.getenv("GROQ_API_KEY", "")

        if not self.token:
            raise ValueError("GROQ_API_KEY is not set in .env")

        self.client = Groq(api_key=self.token)
        self.max_steps = 10

    def _call_apertus(self, messages: List[Dict[str, Any]]) -> Any:
        response = self.client.chat.completions.create(
            model=self.model_id,
            messages=messages,
            tools=TOOLS_SCHEMA,
            tool_choice="auto",
            max_tokens=3000,
            temperature=0.3,
            top_p=0.9,
        )
        return response.choices[0].message

    def _run_agent_loop(self, system_prompt: str, user_message: str) -> str:
        """Generic agent loop with mandatory workflow enforcement."""
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        # Track which tools have been called
        called_tools: List[str] = []
        detect_fraud_called = False
        nudge_count = 0
        max_nudges = 3

        for step in range(self.max_steps):
            print(f"\n--- Step {step + 1} ---")
            message = self._call_apertus(messages)
            print(f"Assistant content: {message.content!r}")
            print(f"Tool calls: {message.tool_calls!r}")

            # If no tool calls AND detect_fraud was not called -> nudge the agent
            if not message.tool_calls:
                if not detect_fraud_called and nudge_count < max_nudges:
                    nudge_count += 1
                    print(f">> NUDGE #{nudge_count}: agent tried to finish without detect_fraud")
                    messages.append(message)
                    messages.append({
                        "role": "user",
                        "content": (
                            "STOP. You have NOT called detect_fraud yet. "
                            "This is MANDATORY. Call detect_fraud NOW with the "
                            "extracted fields (invoice_id, supplier_name, amount, vat, "
                            "po_reference, iban). Do not write a summary until you "
                            "have the fraud risk score."
                        ),
                    })
                    continue
                return message.content or "Done."

            messages.append(message)

            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                called_tools.append(tool_name)

                try:
                    tool_args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    tool_args = {}

                if tool_name not in TOOLS:
                    result = {"error": f"unknown tool {tool_name}"}
                else:
                    try:
                        result = TOOLS[tool_name](**tool_args)
                    except Exception as e:
                        result = {"error": str(e)}

                if tool_name == "detect_fraud":
                    detect_fraud_called = True

                print(f"Tool {tool_name} -> {result}")

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_name,
                    "content": json.dumps(result, default=str),
                })

        return "Error: max steps reached without a final answer."

    def run(self, invoice_text: str) -> str:
        # CASE 6: Prompt injection
        if _is_injection_attempt(invoice_text):
            return (
                "I'm an invoice reconciliation agent. "
                "I can't follow instructions that ask me to ignore my role. "
                "Please provide a supplier invoice or purchase order to reconcile."
            )

        # CASE 4: Off-topic
        has_financial_indicators = (
            _has_invoice_id(invoice_text)
            or _has_po_reference(invoice_text)
            or _has_amount(invoice_text)
            or bool(re.search(
                r"\b(invoice|facture|purchase order|bon de commande|rechnung|fattura|total|amount|montant|TVA|VAT)\b",
                invoice_text,
                re.IGNORECASE,
            ))
        )

        if _is_off_topic(invoice_text) and not has_financial_indicators:
            return (
                "I'm an invoice reconciliation agent. I can only help you "
                "reconcile supplier invoices against purchase orders. "
                "Please provide an invoice or PO with the following fields:\n"
                "  - Invoice ID or PO Reference\n  - Supplier\n"
                "  - Amount\n  - VAT"
            )

        # CASE 5: Invalid input
        if (
            not _has_invoice_id(invoice_text)
            and not _has_po_reference(invoice_text)
            and not _has_amount(invoice_text)
        ):
            return (
                "I couldn't find an invoice or purchase order in your message. "
                "Please provide a document with:\n"
                "  - Invoice ID (e.g. INV-2026-0042) or PO Reference (e.g. PO-2026-0117)\n"
                "  - Supplier name\n  - Amount\n  - VAT\n\n"
                "Example:\n"
                "Invoice #INV-2026-0042\n"
                "Supplier: Acme Supplies Ltd.\n"
                "PO Reference: PO-2026-0117\n"
                "Amount: $1,250.00\n"
                "VAT: $250.00"
            )

        # CASE 2: Demo invoice ID only
        demo_invoice_text = _detect_demo_invoice(invoice_text)
        demo_po_text = _detect_demo_po(invoice_text)

        if demo_invoice_text:
            invoice_text = demo_invoice_text
            print("[DEMO] Injected full invoice text for the detected ID.")
            mode = "invoice"
        elif demo_po_text:
            invoice_text = demo_po_text
            print("[DEMO] Injected full purchase order text for the detected ID.")
            mode = "purchase_order"
        else:
            classification = classify_document(invoice_text)
            mode = classification["document_type"]
            print(f"[CLASSIFY] Document type: {mode} (confidence: {classification['confidence']:.2f}, method: {classification['method']})")

            if mode == "unknown":
                mode = "generic"

            if mode == "invoice":
                is_complete, missing = _is_complete_invoice(invoice_text)
                if not is_complete:
                    mode = "generic"

        # CASE 1: Run the appropriate workflow
        if mode == "invoice":
            system_prompt = """You are an autonomous Invoice Reconciliation Agent with fraud detection capabilities.

You have access to these tools:
1. extract_generic - UNIVERSAL EXTRACTION (call FIRST).
2. find_purchase_order - Find a PO in the database.
3. compare_amounts - Compare invoice amounts/VAT against the PO.
4. detect_fraud - Check for fraud signals. RETURNS THE RISK SCORE.
5. send_alert - Send an alert when anomalies are detected.
6. mark_as_approved - Mark the invoice as approved.

============================================================
MANDATORY WORKFLOW - YOU MUST CALL EVERY TOOL BELOW IN ORDER
============================================================
STEP 1: Call extract_generic with the FULL invoice text.
STEP 2: Call find_purchase_order with the extracted po_reference.
STEP 3: Call compare_amounts with the amounts from step 1 and step 2.
STEP 4: Call detect_fraud with ALL extracted fields:
        - invoice_id
        - supplier_name
        - amount
        - vat
        - po_reference (may be null)
        - iban (may be null)
        *** DO NOT SKIP THIS STEP. It is the most important. ***
STEP 5: Based on the fraud score from step 4:
        - score >= 70 OR level CRITICAL -> call send_alert (critical fraud risk)
        - score >= 40 OR level HIGH -> call send_alert (high fraud risk)
        - score >= 20 OR level MEDIUM -> call send_alert (manual review)
        - amounts mismatch -> call send_alert
        - everything matches AND score < 20 -> call mark_as_approved

============================================================
RULES
============================================================
- You MUST call detect_fraud on EVERY invoice. No exceptions.
- You MUST call send_alert OR mark_as_approved at the end.
- If you finish without calling detect_fraud, the analysis is INVALID.
- Your final summary MUST include:
  * The fraud risk score (e.g. "Risk score: 55/100")
  * The fraud risk level (LOW / MEDIUM / HIGH / CRITICAL)
  * The list of detected anomalies (if any)
  * The decision (approved / alerted / escalated)

Use the tools step by step. Reply with a clear summary in plain text."""

            return self._run_agent_loop(
                system_prompt,
                f"Reconcile this invoice:\n\n{invoice_text}",
            )

        if mode == "purchase_order":
            system_prompt = """You are an autonomous Purchase Order (PO) Analyzer.

You have access to these tools:
1. extract_generic - UNIVERSAL EXTRACTION (call FIRST).
2. find_purchase_order - Verify a PO exists in the database.

WORKFLOW (purchase order):
1. Call extract_generic FIRST with the FULL PO text.
2. Call find_purchase_order with the extracted document_reference.
3. Report all extracted fields (reference, supplier, amount, currency, vat, items, dates).
4. Note if the PO is missing from the database.
5. Give a short assessment: is this PO valid and complete?

When done, reply with a clear summary in plain text."""

            return self._run_agent_loop(
                system_prompt,
                f"Analyze this purchase order:\n\n{invoice_text}",
            )

        # Generic / unknown
        system_prompt = """You are a universal Financial Document Analyzer.

You have access to:
1. extract_generic - UNIVERSAL EXTRACTION: extract ALL fields from ANY financial document.
2. classify_document - Classify the document type.

WORKFLOW (any document):
1. Call extract_generic FIRST with the FULL document text.
2. Call classify_document if the type is unclear.
3. Report all extracted fields (document_type, reference, supplier, amount, currency, vat, dates, iban, items).
4. If the document is NOT a financial document, say so clearly.
5. If some fields are missing, ask the user to provide them.

When done, reply with a clear summary in plain text."""

        return self._run_agent_loop(
            system_prompt,
            f"Analyze this document:\n\n{invoice_text}",
        )


__all__ = ["ApertusInvoiceAgent"]