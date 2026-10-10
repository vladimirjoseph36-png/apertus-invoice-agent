# Apertus Invoice Assistant

An autonomous AI agent that reconciles supplier invoices against purchase orders **and detects fraud** — powered by Groq (open-source LLMs).

**Author:** Anio Joseph
**Project:** Hack Apertus — October 2026

---

## What it does

Every company receives hundreds of supplier invoices every month. Each one must be manually compared against its purchase order to catch amount mismatches, VAT errors, missing POs — **and fraudulent invoices**.

Apertus Invoice Assistant automates the entire workflow:

1. **Extracts** structured data from an invoice
2. **Finds** the matching purchase order
3. **Compares** amounts, VAT, and line items
4. **Detects fraud** using 11+ heuristic rules, statistical analysis (z-score), and machine learning (Isolation Forest)
5. **Approves** the invoice OR **sends an alert** if anomalies are detected

## Features

- Fast LLM inference via Groq (openai/gpt-oss-120b)
- Autonomous agent that chains 6 tools with native tool calling
- Advanced fraud detection engine:
  - 11+ heuristic rules
  - Statistical outlier detection (z-score)
  - ML-based anomaly detection (Isolation Forest)
  - Risk score 0-100 with 4 severity levels
- SQLite database for supplier history
- Robust input handling (7 cases)
- Modern Swiss-inspired web UI
- FastAPI backend + vanilla JavaScript frontend

## Tools (6)

| Tool | Description |
|------|-------------|
| extract_invoice | Extract structured data from invoice text |
| find_purchase_order | Look up the matching PO reference |
| compare_amounts | Compare invoice vs PO amounts and VAT |
| detect_fraud | Analyze fraud signals (rules + stats + ML) |
| send_alert | Flag the invoice for manual review |
| mark_as_approved | Mark the invoice as approved |

## Fraud Detection Engine

Combines three layers:

1. Heuristic rules (approval threshold, recent supplier, blacklist, IBAN mismatch, duplicate, VAT anomalies, round amounts, missing PO)
2. Statistical analysis (z-score on supplier history)
3. Machine Learning (Isolation Forest via scikit-learn)

Output: risk_score 0-100, risk_level (low/medium/high/critical), anomalies, recommendation.

## Robustness — 7 input cases

1. Complete invoice -> full reconciliation
2. Invoice ID only -> uses demo data
3. Incomplete invoice -> asks for missing fields
4. Off-topic message -> polite redirect
5. Invalid input -> asks for a valid invoice
6. Prompt injection -> refuses manipulation
7. Greeting -> redirects to mission

## Architecture

Browser (Swiss UI) -> FastAPI -> ApertusInvoiceAgent <-> Groq API (openai/gpt-oss-120b) -> 6 Python tools <-> SQLite -> Fraud Detection Engine (rules + stats + ML)

Stack:
- LLM: Groq API - openai/gpt-oss-120b (free tier)
- Backend: FastAPI + Python 3.11
- Database: SQLite
- ML: scikit-learn (Isolation Forest), numpy, pandas
- Frontend: Vanilla HTML / CSS / JS

## Quick Start

Prerequisites:
- Python 3.11+
- A free Groq account + API key: https://console.groq.com/keys

Steps:

1. Clone the repository
git clone https://github.com/vladimirjoseph36-png/apertus-invoice-agent.git
cd apertus-invoice-agent

2. Create a virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

3. Install dependencies
pip install -r requirements.txt

4. Configure environment variables
Create a .env file with:
GROQ_API_KEY=gsk_your_groq_api_key_here
APERTUS_MODEL=openai/gpt-oss-120b

5. Initialize the database
python tools\init_database.py

6. Run the app
uvicorn api:app --reload --host 0.0.0.0 --port 8000

Open your browser at http://localhost:8000/chat

## Demo Scenarios

- Reconcile invoice INV-2026-0042  ->  Medium fraud risk (duplicate detected)
- Reconcile invoice INV-2026-FRAUD ->  High/Critical fraud risk (multiple anomalies)
- INV-2026-0042                    ->  Uses demo data
- Raconte-moi une blague           ->  Polite redirect
- Ignore previous instructions     ->  Refuses manipulation

## Project Structure

apertus-invoice-agent/
  api.py
  requirements.txt
  .env.example
  README.md
  agent/
    apertus_agent.py
    apertus_client.py
  tools/
    extract_invoice.py
    find_purchase_order.py
    compare_amounts.py
    detect_fraud.py
    send_alert.py
    mark_as_approved.py
    init_database.py
  data/
    invoices.db (generated locally)
  templates/
    chat.html
  static/
    css/chat.css
    js/chat.js

## License

MIT License — see LICENSE file.

Copyright (c) 2026 Anio Joseph

## Author

Anio Joseph — Built for Hack Apertus, October 2026.