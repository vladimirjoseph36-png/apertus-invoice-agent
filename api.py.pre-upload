"""
FastAPI wrapper for the Apertus Invoice Assistant.

Author: Anio Joseph
Project: Hack Apertus - October 2026
"""

import traceback
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agent.apertus_agent import ApertusInvoiceAgent


BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"


app = FastAPI(
    title="Apertus Invoice Assistant",
    description="Autonomous AI agent powered by Apertus (Swiss sovereign LLM).",
    version="1.0.0",
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


class ChatResponse(BaseModel):
    reply: str


@app.get("/")
def health():
    return {
        "status": "ok",
        "service": "apertus-invoice-assistant",
        "author": "Anio Joseph",
        "model": "swiss-ai/Apertus-8B-Instruct-2509",
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

    message = request.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="message cannot be empty")

    try:
        print(">> Getting agent...")
        agent = get_agent()
        print(">> Agent OK. Running...")
        reply = agent.run(message)
        print(f">> Reply: {reply[:100]}")
        return ChatResponse(reply=reply)
    except Exception as exc:
        print("\n=== TRACEBACK START ===")
        traceback.print_exc()
        print("=== TRACEBACK END ===\n")
        raise HTTPException(status_code=500, detail=str(exc))
