"""
Apertus Invoice Agent - Robust agent using Groq (OpenAI-compatible API).

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


TOOLS: Dict[str, Callable] = {
    "extract_invoice": extract_invoice,
    "find_purchase_order": find_purchase_order,
    "compare_amounts": compare_amounts,
    "send_alert": send_alert,
    "mark_as_approved": mark_as_approved,
    "detect_fraud": detect_fraud,
}

# Schemas JSON pour le tool calling natif Groq
TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "extract_invoice",
            "description": "Extract structured data from an invoice text.",
            "parameters": {
                "type": "object",
                "properties": {
                    "invoice_text": {
                        "type": "string",
                        "description": "The full invoice text to extract data from.",
                    }
                },
                "required": ["invoice_text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_purchase_order",
            "description": "Find a purchase order by its reference.",
            "parameters": {
                "type": "object",
                "properties": {
                    "po_reference": {
                        "type": "string",
                        "description": "The purchase order reference (e.g. PO-2026-0117).",
                    }
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
            "description": "Analyze an invoice for fraud signals (heuristic rules + statistical analysis + ML). Returns a risk score 0-100, level, and detailed anomalies.",
            "parameters": {
                "type": "object",
                "properties": {
                    "invoice_id": {"type": "string"},
                    "supplier_name": {"type": "string"},
                    "amount": {"type": "number"},
                    "vat": {"type": "number"},
                    "po_reference": {"type": "string"},
                    "iban": {"type": "string"},
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

TOOLS_DESCRIPTION = """
Available tools:
1. extract_invoice(invoice_text: str) -> dict
2. find_purchase_order(po_reference: str) -> dict
3. compare_amounts(invoice_amount, invoice_vat, po_amount, po_vat) -> dict
4. detect_fraud(invoice_id, supplier_name, amount, vat, po_reference, iban) -> dict
5. send_alert(invoice_id: str, reason: str) -> dict
6. mark_as_approved(invoice_id: str) -> dict
"""

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

OFF_TOPIC_KEYWORDS = [
    "blague", "joke", "chanson", "song", "poeme", "poem",
    "meteo", "weather", "recette", "recipe", "politique", "politics",
    "sport", "football", "film", "movie", "musique", "music",
    "raconte", "tell me", "explique-moi", "explain to me",
    "bonjour", "salut", "hello", "hi ", "hey ",
    "qui es-tu", "who are you", "ca va", "how are you",
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
                "Amount:" in text
                or "Supplier:" in text
                or "PO Reference:" in text
            )
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
        self.model_id = os.getenv(
            "APERTUS_MODEL",
            "openai/gpt-oss-120b",
        )
        self.token = os.getenv("GROQ_API_KEY", "")

        if not self.token:
            raise ValueError("GROQ_API_KEY is not set in .env")

        self.client = Groq(api_key=self.token)
        self.max_steps = 8

    def _call_apertus(self, messages: List[Dict[str, Any]]) -> Any:
        """Call Groq with native tool calling."""
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

    def run(self, invoice_text: str) -> str:
        # CASE 6: Prompt injection
        if _is_injection_attempt(invoice_text):
            return (
                "I'm an invoice reconciliation agent. "
                "I can't follow instructions that ask me to ignore my role. "
                "Please provide a supplier invoice to reconcile."
            )

        # CASE 4: Off-topic
        if _is_off_topic(invoice_text):
            return (
                "I'm an invoice reconciliation agent. I can only help you "
                "reconcile supplier invoices against purchase orders. "
                "Please provide an invoice with the following fields:\n"
                "  - Invoice ID\n  - Supplier\n  - PO Reference\n"
                "  - Amount\n  - VAT"
            )

        # CASE 5: Invalid input
        if not _has_invoice_id(invoice_text) and not _has_amount(invoice_text):
            return (
                "I couldn't find an invoice in your message. "
                "Please provide a supplier invoice with:\n"
                "  - Invoice ID (e.g. INV-2026-0042)\n"
                "  - Supplier name\n  - PO Reference\n"
                "  - Amount\n  - VAT\n\n"
                "Example:\n"
                "Invoice #INV-2026-0042\n"
                "Supplier: Acme Supplies Ltd.\n"
                "PO Reference: PO-2026-0117\n"
                "Amount: $1,250.00\n"
                "VAT: $250.00"
            )

        # CASE 2: Demo ID only
        demo_text = _detect_demo_invoice(invoice_text)
        if demo_text:
            invoice_text = demo_text
            print("[DEMO] Injected full invoice text for the detected ID.")
        else:
            # CASE 3: Incomplete invoice
            is_complete, missing = _is_complete_invoice(invoice_text)
            if not is_complete:
                missing_str = "\n".join(f"  - {field}" for field in missing)
                return (
                    "I found an invoice, but some required fields are missing:\n"
                    f"{missing_str}\n\n"
                    "Please provide the missing information so I can reconcile it."
                )

        # CASE 1: Complete invoice -> run the agent
        system_prompt = """You are an autonomous Invoice Reconciliation Agent with fraud detection capabilities.

You have access to these tools:
1. extract_invoice - Extract structured data from an invoice text.
2. find_purchase_order - Find a purchase order by its reference.
3. compare_amounts - Compare invoice amounts/VAT against the PO.
4. detect_fraud - Check for fraud signals (returns risk score 0-100).
5. send_alert - Send an alert when anomalies are detected.
6. mark_as_approved - Mark the invoice as approved when everything matches.

WORKFLOW:
1. Call extract_invoice with the FULL invoice text.
2. Call find_purchase_order to locate the PO.
3. Call compare_amounts to check for anomalies.
4. Call detect_fraud to check for fraud signals (CRITICAL STEP).
5. Based on results:
   - If fraud risk is HIGH or CRITICAL -> call send_alert with a detailed reason (mention the risk score and top anomalies).
   - If amounts mismatch -> call send_alert.
   - If everything matches AND fraud risk is LOW -> call mark_as_approved.
   - If fraud risk is MEDIUM -> call send_alert with the warnings for manual review.

IMPORTANT: Always include the fraud risk score and level in your final summary.

Use the tools step by step. When done, reply with a clear summary in plain text."""

        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Reconcile this invoice:\n\n{invoice_text}"},
        ]

        for step in range(self.max_steps):
            print(f"\n--- Step {step + 1} ---")
            message = self._call_apertus(messages)
            print(f"Assistant content: {message.content!r}")
            print(f"Tool calls: {message.tool_calls!r}")

            # Si le modele a fini et repond en texte
            if not message.tool_calls:
                return message.content or "Done."

            # Ajouter le message assistant (avec tool_calls) a l'historique
            messages.append(message)

            # Executer chaque tool call
            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
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

                print(f"Tool {tool_name} -> {result}")

                # Reponse de l'outil dans le format Groq/OpenAI
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_name,
                    "content": json.dumps(result),
                })

        return "Error: max steps reached without a final answer."


__all__ = ["ApertusInvoiceAgent"]