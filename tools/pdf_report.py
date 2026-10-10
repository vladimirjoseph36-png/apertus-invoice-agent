"""
Professional PDF report generator for invoice analysis.

Produces a clean, A4, English-language report with:
1. Executive summary
2. Document information
3. Financial details
4. PO comparison
5. Fraud detection results
6. Recommendation

Author: Anio Joseph
Project: Hack Apertus - October 2026
"""

from __future__ import annotations

import json
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


SWISS_RED = colors.HexColor("#E30613")
DARK = colors.HexColor("#1A1A1A")
GREY = colors.HexColor("#666666")
LIGHT_GREY = colors.HexColor("#F5F5F5")
GREEN = colors.HexColor("#22C55E")
YELLOW = colors.HexColor("#F59E0B")
ORANGE = colors.HexColor("#F97316")
RED = colors.HexColor("#DC2626")


def _risk_color(level: str) -> colors.Color:
    return {
        "low": GREEN,
        "medium": YELLOW,
        "high": ORANGE,
        "critical": RED,
    }.get((level or "low").lower(), GREY)


def _risk_icon(level: str) -> str:
    return {
        "low": "[OK]",
        "medium": "[!]",
        "high": "[!!]",
        "critical": "[!!!]",
    }.get((level or "low").lower(), "[?]")


def _decision_label(decision: str) -> str:
    return {
        "approved": "APPROVED",
        "alerted": "ALERT - MANUAL REVIEW REQUIRED",
        "escalated": "ESCALATED - CRITICAL FRAUD RISK",
    }.get((decision or "").lower(), "REVIEW REQUIRED")


def _fmt_amount(amount: Optional[float], currency: Optional[str] = "CHF") -> str:
    if amount is None:
        return "N/A"
    return f"{amount:,.2f} {currency or 'CHF'}"


def generate_report_pdf(analysis: Dict[str, Any]) -> bytes:
    """Generate a PDF report from an analysis dict. Returns PDF bytes."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title="Invoice Analysis Report",
        author="Apertus Invoice Assistant",
    )

    styles = getSampleStyleSheet()
    story = []

    h1 = ParagraphStyle(
        "H1", parent=styles["Heading1"],
        fontSize=20, textColor=SWISS_RED, spaceAfter=2, alignment=1,
        fontName="Helvetica-Bold",
    )
    h2 = ParagraphStyle(
        "H2", parent=styles["Heading2"],
        fontSize=13, textColor=DARK, spaceBefore=14, spaceAfter=6,
        fontName="Helvetica-Bold",
    )
    body = ParagraphStyle(
        "Body", parent=styles["BodyText"],
        fontSize=10, textColor=DARK, leading=14,
    )
    small = ParagraphStyle(
        "Small", parent=styles["BodyText"],
        fontSize=8, textColor=GREY, leading=11,
    )
    summary_title = ParagraphStyle(
        "SumTitle", parent=styles["BodyText"],
        fontSize=14, textColor=colors.white, fontName="Helvetica-Bold",
        alignment=1,
    )
    summary_body = ParagraphStyle(
        "SumBody", parent=styles["BodyText"],
        fontSize=10, textColor=colors.white, alignment=1, leading=14,
    )

    # Header
    story.append(Paragraph("APERTUS", h1))
    story.append(Paragraph("Invoice Analysis Report", ParagraphStyle(
        "Sub", parent=styles["BodyText"], fontSize=11, textColor=GREY,
        alignment=1, spaceAfter=4,
    )))
    story.append(Paragraph(
        "Autonomous reconciliation & fraud detection - Hack Apertus 2026",
        ParagraphStyle("Sub2", parent=styles["BodyText"], fontSize=8,
                       textColor=GREY, alignment=1),
    ))
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=1.5, color=SWISS_RED))
    story.append(Spacer(1, 12))

    # Executive Summary
    risk_score = analysis.get("risk_score") or 0
    risk_level = (analysis.get("risk_level") or "low").lower()
    decision = (analysis.get("decision") or "review").lower()
    color = _risk_color(risk_level)
    icon = _risk_icon(risk_level)

    summary_data = [
        [Paragraph(f"{icon} {_decision_label(decision)}", summary_title)],
        [Paragraph(
            f"Amount analyzed: <b>{_fmt_amount(analysis.get('amount'), analysis.get('currency'))}</b>"
            f" &nbsp;|&nbsp; Risk score: <b>{risk_score}/100</b> ({risk_level.upper()})",
            summary_body,
        )],
    ]
    summary_table = Table(summary_data, colWidths=[17 * cm])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), color),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 16))

    # 1. Document Information
    story.append(Paragraph("1. Document Information", h2))
    story.append(HRFlowable(width="100%", thickness=0.5, color=LIGHT_GREY))
    story.append(Spacer(1, 6))

    doc_info = [
        ["Type", analysis.get("document_type") or "Unknown"],
        ["Reference", analysis.get("document_reference") or "N/A"],
        ["Supplier", analysis.get("supplier_name") or "N/A"],
        ["Currency", analysis.get("currency") or "N/A"],
        ["PO Reference", analysis.get("po_reference") or "None"],
    ]
    doc_table = Table(doc_info, colWidths=[4.5 * cm, 12.5 * cm])
    doc_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TEXTCOLOR", (0, 0), (0, -1), GREY),
        ("TEXTCOLOR", (1, 0), (1, -1), DARK),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(doc_table)
    story.append(Spacer(1, 10))

    # 2. Financial Details
    story.append(Paragraph("2. Financial Details", h2))
    story.append(HRFlowable(width="100%", thickness=0.5, color=LIGHT_GREY))
    story.append(Spacer(1, 6))

    amount = analysis.get("amount")
    vat = analysis.get("vat")
    currency = analysis.get("currency") or "CHF"
    net = (amount - vat) if (amount is not None and vat is not None) else None

    fin_info = [
        ["Net amount (HT)", _fmt_amount(net, currency)],
        ["VAT", _fmt_amount(vat, currency)],
        ["Total (TTC)", _fmt_amount(amount, currency)],
    ]
    fin_table = Table(fin_info, colWidths=[4.5 * cm, 12.5 * cm])
    fin_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TEXTCOLOR", (0, 0), (0, -1), GREY),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(fin_table)
    story.append(Spacer(1, 10))

    # 3. PO Comparison
    story.append(Paragraph("3. Purchase Order Comparison", h2))
    story.append(HRFlowable(width="100%", thickness=0.5, color=LIGHT_GREY))
    story.append(Spacer(1, 6))

    po_ref = analysis.get("po_reference")
    if po_ref:
        story.append(Paragraph(
            f"Purchase order <b>{po_ref}</b> was located in the system. "
            f"Amounts and VAT were compared automatically.",
            body,
        ))
    else:
        story.append(Paragraph(
            "No purchase order was found for this document. "
            "This is a potential fraud signal (missing PO).",
            body,
        ))
    story.append(Spacer(1, 10))

    # 4. Fraud Detection
    story.append(Paragraph("4. Fraud Detection", h2))
    story.append(HRFlowable(width="100%", thickness=0.5, color=LIGHT_GREY))
    story.append(Spacer(1, 6))

    story.append(Paragraph(
        f"<b>Global risk score:</b> {risk_score}/100 "
        f"&mdash; Level: <font color='{color.hexval()}'><b>{risk_level.upper()}</b></font>",
        body,
    ))
    story.append(Spacer(1, 6))

    fraud_json = analysis.get("fraud_json")
    anomalies = []
    if fraud_json:
        try:
            fraud_data = json.loads(fraud_json) if isinstance(fraud_json, str) else fraud_json
            anomalies = fraud_data.get("anomalies", [])
        except Exception:
            anomalies = []

    if anomalies:
        story.append(Paragraph("<b>Anomalies detected:</b>", body))
        story.append(Spacer(1, 4))
        for a in anomalies:
            sev = (a.get("severity") or "low").upper()
            msg = a.get("message") or a.get("code") or "Unknown anomaly"
            story.append(Paragraph(f"&bull; [{sev}] {msg}", body))
        story.append(Spacer(1, 8))
    else:
        story.append(Paragraph(
            "No fraud signals were detected. The document appears consistent with "
            "the supplier's historical behavior.",
            body,
        ))
        story.append(Spacer(1, 8))

    # 5. Recommendation
    story.append(Paragraph("5. Recommendation", h2))
    story.append(HRFlowable(width="100%", thickness=0.5, color=LIGHT_GREY))
    story.append(Spacer(1, 6))

    rec_map = {
        "approved": "The invoice can be <b>approved</b> and processed normally.",
        "alerted": "The invoice requires <b>manual verification</b> before approval. "
                   "Review the anomalies listed above with the finance team.",
        "escalated": "<b>Do not approve this invoice.</b> Escalate immediately to the "
                     "finance department and the fraud prevention team.",
    }
    rec_text = rec_map.get(decision, "Manual review is recommended.")
    rec_color = _risk_color(risk_level)
    rec_table = Table([[Paragraph(rec_text, ParagraphStyle(
        "Rec", parent=body, fontSize=11, textColor=colors.white,
    ))]], colWidths=[17 * cm])
    rec_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), rec_color),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
    ]))
    story.append(rec_table)

    # Footer
    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=0.5, color=LIGHT_GREY))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        f"Report generated on {datetime.now().strftime('%Y-%m-%d at %H:%M')} "
        f"by Apertus Invoice Assistant. Analysis ID: {analysis.get('id', 'N/A')}",
        small,
    ))
    story.append(Paragraph(
        "This report is provided for informational purposes. The final decision "
        "remains with the finance team.",
        small,
    ))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


if __name__ == "__main__":
    sample = {
        "id": "test-001",
        "document_type": "invoice",
        "document_reference": "INV-2026-0042",
        "supplier_name": "Acme Supplies Ltd.",
        "amount": 1250.00,
        "currency": "USD",
        "vat": 250.00,
        "po_reference": "PO-2026-0117",
        "risk_score": 30,
        "risk_level": "medium",
        "decision": "alerted",
        "fraud_json": json.dumps({
            "anomalies": [
                {"severity": "high", "message": "Possible duplicate with INV-2026-0038"},
            ]
        }),
    }
    pdf = generate_report_pdf(sample)
    with open("test_report.pdf", "wb") as f:
        f.write(pdf)
    print(f"[OK] Test PDF generated: test_report.pdf ({len(pdf)} bytes)")