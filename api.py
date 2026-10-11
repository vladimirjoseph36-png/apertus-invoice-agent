"""
FastAPI wrapper for the Apertus Invoice Assistant.

Supports text chat + file upload (OCR) + PDF report generation.

Author: Anio Joseph
Project: Hack Apertus - October 2026
"""

import json
import os
import re
import shutil
import sqlite3
import tempfile
import traceback
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agent.apertus_agent import ApertusInvoiceAgent, DEMO_INVOICES, DEMO_PURCHASE_ORDERS
from tools.ocr_engine import check_ocr_available, extract_text_from_file
from tools.pdf_report import generate_report_pdf
from tools.extract_generic import extract_generic


BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
UPLOAD_DIR = BASE_DIR / "uploads"
DB_PATH = BASE_DIR / "data" / "invoices.db"
UPLOAD_DIR.mkdir(exist_ok=True)


app = FastAPI(
    title="Apertus Invoice Assistant",
    description="Autonomous AI agent powered by Apertus (Swiss sovereign LLM).",
    version="1.3.0",
)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


_agent = None


def get_agent():
    global _agent
    if _agent is None:
        _agent = ApertusInvoiceAgent()
    return _agent


class ChatRequest(BaseModel):
    message: str
    save_analysis: bool = False


class ChatResponse(BaseModel):
    reply: str
    analysis_id: str | None = None


class UploadResponse(BaseModel):
    success: bool
    text: str
    filename: str
    size_kb: float
    error: str | None = None


ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp", ".pdf"}
MAX_FILE_SIZE = 20 * 1024 * 1024


# ----------------------------------------------------------------------
# Helpers DB
# ----------------------------------------------------------------------

def _save_analysis_row(analysis: dict) -> str:
    """Save an analysis to the DB. Returns the analysis ID."""
    analysis_id = analysis.get("id") or str(uuid.uuid4())
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    cur.execute("""
        INSERT OR REPLACE INTO analyses
        (id, created_at, source, document_type, document_reference,
         supplier_name, amount, currency, vat, po_reference,
         fields_json, fraud_json, risk_score, risk_level, decision, raw_text)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        analysis_id,
        analysis.get("created_at") or datetime.now().isoformat(),
        analysis.get("source", "chat"),
        analysis.get("document_type"),
        analysis.get("document_reference"),
        analysis.get("supplier_name"),
        analysis.get("amount"),
        analysis.get("currency"),
        analysis.get("vat"),
        analysis.get("po_reference"),
        analysis.get("fields_json"),
        analysis.get("fraud_json"),
        analysis.get("risk_score"),
        analysis.get("risk_level"),
        analysis.get("decision"),
        analysis.get("raw_text"),
    ))
    conn.commit()
    conn.close()
    return analysis_id


def _get_analysis(analysis_id: str) -> dict | None:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM analyses WHERE id = ?", (analysis_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return dict(row)


def _guess_decision(reply: str) -> str:
    r = (reply or "").lower()
    if "escalat" in r or "critical" in r or "do not approve" in r:
        return "escalated"
    if "alert" in r or "manual" in r or "review" in r:
        return "alerted"
    if "approved" in r or "approve" in r:
        return "approved"
    return "review"


def _guess_risk_level(reply: str) -> str:
    r = (reply or "").lower()
    if "critical" in r:
        return "critical"
    if "high" in r:
        return "high"
    if "medium" in r:
        return "medium"
    return "low"


def _guess_risk_score(reply: str) -> int:
    """Extract the risk score from the agent reply."""
    text = reply or ""

    m = re.search(r"(\d+)\s*/\s*100", text)
    if m:
        return int(m.group(1))

    m = re.search(r"risk\s*score[^\d]{0,20}(\d+)", text, re.IGNORECASE)
    if m:
        return int(m.group(1))

    m = re.search(r"score\s*de\s*risque[^\d]{0,20}(\d+)", text, re.IGNORECASE)
    if m:
        return int(m.group(1))

    r = text.lower()
    if "critical" in r:
        return 85
    if "high" in r:
        return 65
    if "medium" in r:
        return 35
    if "low" in r:
        return 10

    return 0


def _extract_fraud_json(reply: str) -> str | None:
    """
    Extract fraud anomalies from the agent reply.
    Tries 3 strategies:
    1. Extract the raw dict from "Tool detect_fraud -> {...}"
    2. Look for anomaly codes (UNKNOWN_SUPPLIER, etc.)
    3. Parse the "Key Anomalies" section from the summary text
    """
    text = reply or ""

    # STRATEGY 1: Extract the raw dict from "Tool detect_fraud -> {...}"
    m = re.search(r"Tool detect_fraud -> (\{.*?\})(?:\s*\n|$)", text, re.DOTALL)
    if m:
        raw = m.group(1)
        # Try direct JSON parse
        try:
            parsed = json.loads(raw)
            return json.dumps(parsed)
        except Exception:
            pass
        # Try converting single quotes to double quotes
        try:
            raw2 = raw.replace("'", '"')
            parsed = json.loads(raw2)
            return json.dumps(parsed)
        except Exception:
            pass
        # Try ast.literal_eval
        try:
            import ast
            parsed = ast.literal_eval(raw)
            return json.dumps(parsed)
        except Exception:
            pass

    # STRATEGY 2: Look for anomaly codes in the text
    anomalies = []
    code_map = {
        "POSSIBLE_DUPLICATE": ("high", "Possible duplicate invoice detected"),
        "UNKNOWN_SUPPLIER": ("high", "Unknown supplier"),
        "JUST_UNDER_APPROVAL_THRESHOLD": ("medium", "Amount just under the approval threshold"),
        "IBAN_MISMATCH": ("critical", "IBAN mismatch detected"),
        "ANOMALOUS_VAT_RATE": ("medium", "Anomalous VAT rate"),
        "ROUND_AMOUNT": ("low", "Round amount suspicion"),
        "MISSING_PO": ("medium", "Missing purchase order"),
        "ML_ANOMALY": ("medium", "Anomaly detected by Isolation Forest"),
    }
    for code, (severity, msg) in code_map.items():
        if code in text:
            anomalies.append({"code": code, "severity": severity, "message": msg})

    if anomalies:
        return json.dumps({"anomalies": anomalies})

    # STRATEGY 3: Parse the "Key Anomalies" section from the summary
    # Look for lines like:
    #   **Key Anomalies:**
    #   1. **Amount just below approval threshold** – ...
    #   2. **Unknown supplier** – ...
    section_match = re.search(
        r"(?:key\s*anomalies|anomalies\s*detected|anomalies)[^\n]*\n((?:\s*\d+\..*\n?)+)",
        text,
        re.IGNORECASE,
    )
    if section_match:
        lines = section_match.group(1).strip().split("\n")
        for line in lines:
            title_match = re.search(r"\*\*(.+?)\*\*", line)
            if title_match:
                title = title_match.group(1).strip()
                title_lower = title.lower()
                if any(k in title_lower for k in ("unknown", "not present", "not found", "missing")):
                    severity = "high"
                elif any(k in title_lower for k in ("duplicate", "iban", "threshold", "zero vat", "anomalous", "high")):
                    severity = "medium"
                else:
                    severity = "low"
                anomalies.append({
                    "code": "DETECTED",
                    "severity": severity,
                    "message": title,
                })

    if anomalies:
        return json.dumps({"anomalies": anomalies})

    # STRATEGY 4: Generic fallback — look for bullet points after "anomalies"
    generic_match = re.search(
        r"anomalies[^\n]*\n((?:\s*[•\-\*].*\n?)+)",
        text,
        re.IGNORECASE,
    )
    if generic_match:
        lines = generic_match.group(1).strip().split("\n")
        for line in lines:
            cleaned = line.strip().lstrip("•-*").strip()
            if cleaned:
                anomalies.append({
                    "code": "DETECTED",
                    "severity": "medium",
                    "message": cleaned,
                })

    if anomalies:
        return json.dumps({"anomalies": anomalies})

    return None


def _save_full_analysis(message: str, reply: str, source: str = "chat") -> str:
    """Extract fields from the raw message, then save a complete analysis row."""
    print(">> _save_full_analysis: extracting fields via LLM...")

    text_to_extract = message
    for demo_id, demo_text in DEMO_INVOICES.items():
        if demo_id in message:
            text_to_extract = demo_text
            print(f">> Demo invoice detected: {demo_id}, using full demo text")
            break
    else:
        for demo_id, demo_text in DEMO_PURCHASE_ORDERS.items():
            if demo_id in message:
                text_to_extract = demo_text
                print(f">> Demo PO detected: {demo_id}, using full demo text")
                break

    extraction = extract_generic(text_to_extract)
    fields = extraction.get("fields", {}) if extraction.get("success") else {}
    doc_type = extraction.get("document_type", "unknown")

    print(f">> Extraction success: {extraction.get('success')}")
    print(f">> Document type: {doc_type}")
    print(f">> Fields: {fields}")

    risk_score = _guess_risk_score(reply)
    risk_level = _guess_risk_level(reply)
    fraud_json = _extract_fraud_json(reply)

    print(f">> Extracted risk_score: {risk_score}")
    print(f">> Extracted risk_level: {risk_level}")
    print(f">> Extracted fraud_json: {fraud_json}")

    analysis = {
        "source": source,
        "raw_text": message,
        "document_type": doc_type,
        "document_reference": fields.get("document_reference"),
        "supplier_name": fields.get("supplier_name"),
        "amount": fields.get("amount"),
        "currency": fields.get("currency"),
        "vat": fields.get("vat"),
        "po_reference": fields.get("po_reference"),
        "fields_json": json.dumps(fields, default=str),
        "fraud_json": fraud_json,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "decision": _guess_decision(reply),
    }

    return _save_analysis_row(analysis)


# ----------------------------------------------------------------------
# Routes
# ----------------------------------------------------------------------

@app.get("/")
def health():
    return {
        "status": "ok",
        "service": "apertus-invoice-assistant",
        "author": "Anio Joseph",
        "model": os.getenv("APERTUS_MODEL", "unknown"),
        "ocr": check_ocr_available(),
    }


@app.get("/chat", response_class=HTMLResponse)
def chat_ui():
    template_path = TEMPLATES_DIR / "chat.html"
    if not template_path.exists():
        raise HTTPException(status_code=500, detail="Template chat.html not found")
    return HTMLResponse(content=template_path.read_text(encoding="utf-8"))


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    print("\n=== POST /chat received ===")
    print(f"Message: {request.message!r}")
    print(f"save_analysis: {request.save_analysis}")

    message = request.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="message cannot be empty")

    try:
        agent = get_agent()
        reply = agent.run(message)
        analysis_id = None

        if request.save_analysis:
            try:
                analysis_id = _save_full_analysis(
                    message=message,
                    reply=reply,
                    source="chat",
                )
                print(f">> Analysis saved with ID: {analysis_id}")
            except Exception as e:
                print(f"[WARN] Could not save analysis: {e}")
                traceback.print_exc()

        return ChatResponse(reply=reply, analysis_id=analysis_id)
    except Exception as exc:
        print("\n=== TRACEBACK START ===")
        traceback.print_exc()
        print("=== TRACEBACK END ===\n")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...)):
    print(f"\n=== POST /upload received ===")
    print(f"Filename: {file.filename}")

    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Allowed: {sorted(ALLOWED_EXTS)}",
        )

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext, dir=str(UPLOAD_DIR)) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")
    finally:
        file.file.close()

    size_bytes = os.path.getsize(tmp_path)
    size_kb = round(size_bytes / 1024, 1)

    if size_bytes > MAX_FILE_SIZE:
        os.remove(tmp_path)
        raise HTTPException(status_code=400, detail="File too large (max 20 MB)")

    try:
        result = extract_text_from_file(tmp_path)
    except Exception as e:
        result = {"success": False, "text": "", "error": str(e)}
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass

    if not result.get("success"):
        return UploadResponse(
            success=False, text="", filename=file.filename,
            size_kb=size_kb, error=result.get("error", "OCR failed"),
        )

    return UploadResponse(
        success=True, text=result.get("text", ""),
        filename=file.filename, size_kb=size_kb, error=None,
    )


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_ui():
    template_path = TEMPLATES_DIR / "dashboard.html"
    if not template_path.exists():
        raise HTTPException(status_code=500, detail="Template dashboard.html not found")
    return HTMLResponse(content=template_path.read_text(encoding="utf-8"))


@app.get("/api/stats")
def get_stats():
    """Return aggregate statistics for the dashboard."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) AS n FROM analyses")
    total_docs = cur.fetchone()["n"]

    cur.execute("SELECT COALESCE(SUM(amount), 0) AS total FROM analyses")
    total_amount = cur.fetchone()["total"]

    cur.execute("""
        SELECT risk_level, COUNT(*) AS n
        FROM analyses
        WHERE risk_level IS NOT NULL
        GROUP BY risk_level
    """)
    by_level = {row["risk_level"]: row["n"] for row in cur.fetchall()}

    alerts = by_level.get("medium", 0) + by_level.get("high", 0) + by_level.get("critical", 0)

    cur.execute("""
        SELECT supplier_name, COUNT(*) AS n, COALESCE(SUM(amount), 0) AS total
        FROM analyses
        WHERE supplier_name IS NOT NULL
        GROUP BY supplier_name
        ORDER BY n DESC
        LIMIT 5
    """)
    top_suppliers = [dict(row) for row in cur.fetchall()]

    cur.execute("""
        SELECT id, created_at, document_type, document_reference,
               supplier_name, amount, currency, risk_score, risk_level, decision
        FROM analyses
        ORDER BY created_at DESC
        LIMIT 20
    """)
    recent = [dict(row) for row in cur.fetchall()]

    cur.execute("""
        SELECT created_at, risk_score
        FROM analyses
        WHERE risk_score IS NOT NULL
        ORDER BY created_at ASC
        LIMIT 30
    """)
    scores = [dict(row) for row in cur.fetchall()]

    conn.close()

    return {
        "total_docs": total_docs,
        "total_amount": round(total_amount, 2),
        "alerts": alerts,
        "by_level": by_level,
        "top_suppliers": top_suppliers,
        "recent": recent,
        "scores": scores,
    }


@app.post("/api/clear-analyses")
def clear_analyses():
    """Delete all rows from the analyses table."""
    print("\n=== POST /api/clear-analyses ===")
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    cur.execute("DELETE FROM analyses")
    deleted = cur.rowcount
    conn.commit()
    conn.close()
    print(f">> Deleted {deleted} analyses")
    return {"success": True, "deleted": deleted}


@app.delete("/api/analysis/{analysis_id}")
def delete_analysis(analysis_id: str):
    """Delete a single analysis by ID."""
    print(f"\n=== DELETE /api/analysis/{analysis_id} ===")
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    cur.execute("DELETE FROM analyses WHERE id = ?", (analysis_id,))
    deleted = cur.rowcount
    conn.commit()
    conn.close()
    if deleted == 0:
        raise HTTPException(status_code=404, detail="Analysis not found")
    print(f">> Deleted analysis {analysis_id}")
    return {"success": True, "deleted": deleted, "id": analysis_id}


@app.get("/api/report/{analysis_id}.pdf")
def download_report(analysis_id: str):
    """Generate and return the PDF report for the given analysis."""
    print(f"\n=== GET /api/report/{analysis_id}.pdf ===")
    analysis = _get_analysis(analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    try:
        pdf_bytes = generate_report_pdf(analysis)
    except Exception as e:
        print(f"[ERROR] PDF generation failed: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {e}")

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="apertus_report_{analysis_id[:8]}.pdf"'
        },
    )


@app.get("/api/analysis/{analysis_id}")
def get_analysis_endpoint(analysis_id: str):
    """Return the analysis JSON."""
    analysis = _get_analysis(analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return analysis