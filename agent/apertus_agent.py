"""
Apertus Invoice Agent - Robust agent using Apertus LLM.

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

from huggingface_hub import InferenceClient

from tools.extract_invoice import extract_invoice
from tools.find_purchase_order import find_purchase_order
from tools.compare_amounts import compare_amounts
from tools.send_alert import send_alert
from tools.mark_as_approved import mark_as_approved


TOOLS: Dict[str, Callable] = {
    "extract_invoice": extract_invoice,
    "find_purchase_order": find_purchase_order,
    "compare_amounts": compare_amounts,
    "send_alert": send_alert,
    "mark_as_approved": mark_as_approved,
}

TOOLS_DESCRIPTION = """
Available tools:
1. extract_invoice(invoice_text: str) -> dict
2. find_purchase_order(po_reference: str) -> dict
3. compare_amounts(invoice_amount, invoice_vat, po_amount, po_vat) -> dict
4. send_alert(invoice_id: str, reason: str) -> dict
5. mark_as_approved(invoice_id: str) -> dict
"""

DEMO_INVOICES: Dict[str, str] = {
    "INV-2026-0042": """Invoice #INV-2026-0042
Supplier: Acme Supplies Ltd.
PO Reference: PO-2026-0117
Amount: $1,250.00
VAT: $250.00
Items: 5x Widget A, 2x Widget B
""",
}

# --- Off-topic keywords (FR + EN) ---
OFF_TOPIC_KEYWORDS = [
    "blague", "joke", "chanson", "song", "poème", "poem",
    "météo", "weather", "recette", "recipe", "politique", "politics",
    "sport", "football", "film", "movie", "musique", "music",
    "raconte", "tell me", "explique-moi", "explain to me",
    "bonjour", "salut", "hello", "hi ", "hey ",
    "qui es-tu", "who are you", "ça va", "how are you",
]

# --- Prompt injection keywords ---
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
    """Robust invoice reconciliation agent powered by Apertus."""

    def __init__(self) -> None:
        self.model_id = os.getenv(
            "APERTUS_MODEL",
            "swiss-ai/Apertus-8B-Instruct-2509",
        )
        self.token = os.getenv("HF_TOKEN", "")

        if not self.token:
            raise ValueError("HF_TOKEN is not set in .env")

        self.client = InferenceClient(
            model=self.model_id,
            token=self.token,
            timeout=60,
        )

        self.max_steps = 8

    def _call_apertus(self, messages: List[Dict[str, str]]) -> str:
        response = self.client.chat_completion(
            messages=messages,
            max_tokens=1000,
            temperature=0.3,
            top_p=0.9,
        )
        return response.choices[0].message.content or ""

    def _parse_action(self, text: str) -> Dict[str, Any] | None:
        json_match = re.search(r"\{.*\}", text, re.DOTALL)
        if not json_match:
            return None
        try:
            data = json.loads(json_match.group(0))
        except json.JSONDecodeError:
            return None
        if not isinstance(data, dict):
            return None

        if "final" in data:
            return {"final": data["final"]}

        if "tool" in data and "args" in data:
            return {"tool": data["tool"], "args": data["args"]}

        keys = list(data.keys())
        if len(keys) == 1:
            possible_tool = keys[0]
            if possible_tool in TOOLS:
                args = data[possible_tool]
                if isinstance(args, dict):
                    return {"tool": possible_tool, "args": args}
                return {"tool": possible_tool, "args": {}}

        return None

    def run(self, invoice_text: str) -> str:
        # ==========================================================
        # CASE 6: Prompt injection
        # ==========================================================
        if _is_injection_attempt(invoice_text):
            return (
                "I'm an invoice reconciliation agent. "
                "I can't follow instructions that ask me to ignore my role. "
                "Please provide a supplier invoice to reconcile."
            )

        # ==========================================================
        # CASE 4: Off-topic
        # ==========================================================
        if _is_off_topic(invoice_text):
            return (
                "I'm an invoice reconciliation agent. I can only help you "
                "reconcile supplier invoices against purchase orders. "
                "Please provide an invoice with the following fields:\n"
                "  - Invoice ID\n  - Supplier\n  - PO Reference\n"
                "  - Amount\n  - VAT"
            )

        # ==========================================================
        # CASE 5: Invalid input
        # ==========================================================
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

        # ==========================================================
        # CASE 2: Demo ID only
        # ==========================================================
        demo_text = _detect_demo_invoice(invoice_text)
        if demo_text:
            invoice_text = demo_text
            print("[DEMO] Injected full invoice text for the detected ID.")
        else:
            # ==========================================================
            # CASE 3: Incomplete invoice
            # ==========================================================
            is_complete, missing = _is_complete_invoice(invoice_text)
            if not is_complete:
                missing_str = "\n".join(f"  - {field}" for field in missing)
                return (
                    "I found an invoice, but some required fields are missing:\n"
                    f"{missing_str}\n\n"
                    "Please provide the missing information so I can reconcile it."
                )

        # ==========================================================
        # CASE 1: Complete invoice -> run the agent
        # ==========================================================
        system_prompt = f"""You are an autonomous Invoice Reconciliation Agent.

You have access to these tools:

{TOOLS_DESCRIPTION}

WORKFLOW:
1. Call extract_invoice with the FULL invoice text.
2. Call find_purchase_order to locate the PO.
3. Call compare_amounts to check for anomalies.
4. If anomalies -> call send_alert.
5. If everything matches -> call mark_as_approved.

RESPONSE FORMAT - STRICT:
- To call a tool, respond ONLY with:
  {{"tool": "tool_name", "args": {{...}}}}
- When done, respond ONLY with:
  {{"final": "your summary message"}}

No other text. Only valid JSON."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Reconcile this invoice:\n\n{invoice_text}"},
        ]

        for step in range(self.max_steps):
            print(f"\n--- Step {step + 1} ---")
            response = self._call_apertus(messages)
            print("Apertus:", response[:200])

            action = self._parse_action(response)

            if not action:
                return f"Error: could not parse action from response:\n{response}"

            if "final" in action:
                return action["final"]

            if "tool" in action:
                tool_name = action["tool"]
                tool_args = action.get("args", {})

                if tool_name not in TOOLS:
                    messages.append({"role": "assistant", "content": response})
                    messages.append({
                        "role": "user",
                        "content": f"Error: unknown tool {tool_name}.",
                    })
                    continue

                try:
                    result = TOOLS[tool_name](**tool_args)
                except Exception as e:
                    result = {"error": str(e)}

                print(f"Tool {tool_name} -> {result}")

                messages.append({"role": "assistant", "content": response})
                messages.append({
                    "role": "user",
                    "content": f"Tool result: {json.dumps(result)}",
                })
            else:
                return f"Error: invalid action format: {action}"

        return "Error: max steps reached without a final answer."


__all__ = ["ApertusInvoiceAgent"]
