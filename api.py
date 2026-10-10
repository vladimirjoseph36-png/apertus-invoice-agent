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

from agent.apertus_agent import ApertusInvoiceAgent
from tools.ocr_engine import check_ocr_available, extract_text_from_file
from tools.pdf_report import generate_report_pdf
from tools.extract_generic import extract_generic
from agent.apertus_agent import DEMO_INVOICES, DEMO_PURCHASE_ORDERS


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
    """
    Extract the risk score from the agent reply.
    Tries multiple patterns to handle different formats.
    """
    text = reply or ""

    # Pattern 1: "30 / 100" or "30/100"
    m = re.search(r"(\d+)\s*/\s*100", text)
    if m:
        return int(m.group(1))

    # Pattern 2: "Risk Score:** 30" or "Risk Score: 30"
    m = re.search(r"risk\s*score[^\d]{0,20}(\d+)", text, re.IGNORECASE)
    if m:
        return int(m.group(1))

    # Pattern 3: "Score de risque : 30"
    m = re.search(r"score\s*de\s*risque[^\d]{0,20}(\d+)", text, re.IGNORECASE)
    if m:
        return int(m.group(1))

    # Pattern 4: fallback - use the level to guess a representative score
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


def _save_full_analysis(message: str, reply: str, source: str = "chat") -> str:
    """
    Extract fields from the raw message via extract_generic,
    then save a complete analysis row to the DB.

    If the message contains a demo invoice ID, use the full demo text
    so that all fields are properly extracted.
    """
    print(">> _save_full_analysis: extracting fields via LLM...")

    # Check if the message references a demo invoice/PO
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

    score_match = re.search(r"(\d+)\s*/\s*100", reply or "")
    risk_score = int(score_match.group(1)) if score_match else 0

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
        "fraud_json": None,
        "risk_score": risk_score,
        "risk_level": _guess_risk_level(reply),
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
    """Delete all rows from the analyses table. Used for demo reset."""
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