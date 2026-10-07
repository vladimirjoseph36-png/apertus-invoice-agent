\# Apertus Invoice Assistant



An autonomous AI agent that reconciles supplier invoices against purchase orders — powered by Apertus, Switzerland's sovereign LLM.



\*\*Author:\*\* Anio Joseph

\*\*Project:\*\* Hack Apertus — October 2026



\## What it does



Every company receives hundreds of supplier invoices every month. Each one must be manually compared against its purchase order to catch amount mismatches, VAT errors, and missing POs.



Apertus Invoice Assistant automates the entire workflow:



1\. Extracts structured data from an invoice

2\. Finds the matching purchase order

3\. Compares amounts, VAT, and line items

4\. Approves the invoice OR sends an alert if anomalies are detected



\## Features



\- Powered by Apertus (Swiss sovereign LLM, 8B-Instruct)

\- Autonomous agent that chains 5 tools

\- Robust input handling (7 cases)

\- Modern Swiss-inspired web UI

\- FastAPI backend + vanilla JavaScript frontend

\- 5 tools: extract\_invoice, find\_purchase\_order, compare\_amounts, send\_alert, mark\_as\_approved



\## Robustness — 7 input cases



1\. Complete invoice → full reconciliation

2\. Invoice ID only → uses demo data

3\. Incomplete invoice → asks for missing fields

4\. Off-topic message → polite redirect

5\. Invalid input → asks for a valid invoice

6\. Prompt injection → refuses manipulation

7\. Greeting → redirects to mission



\## Architecture



Browser (Swiss UI) → FastAPI → ApertusInvoiceAgent → Apertus LLM (API)

&#x20;                                         ↓

&#x20;                                    5 Python tools



Stack:

\- LLM: Apertus 8B-Instruct via Hugging Face API

\- Backend: FastAPI + Python 3.11

\- Frontend: Vanilla HTML / CSS / JS

\- Deployment: Render (planned)



\## Quick Start



Prerequisites:

\- Python 3.11+

\- A Hugging Face account + API token (free)



Steps:



1\. Clone the repository

&#x20;  git clone https://github.com/vladimirjoseph36-png/apertus-invoice-agent.git

&#x20;  cd apertus-invoice-agent



2\. Create a virtual environment

&#x20;  python -m venv venv

&#x20;  .\\venv\\Scripts\\Activate.ps1



3\. Install dependencies

&#x20;  pip install -r requirements.txt



4\. Configure environment variables

&#x20;  Create a .env file:

&#x20;  HF\_TOKEN=hf\_your\_huggingface\_token\_here

&#x20;  APERTUS\_MODEL=swiss-ai/Apertus-8B-Instruct-2509



5\. Run the app

&#x20;  uvicorn api:app --reload --host 0.0.0.0 --port 8000



Open your browser at http://localhost:8000/chat



\## Project Structure



apertus-invoice-agent/

&#x20; api.py

&#x20; requirements.txt

&#x20; .env.example

&#x20; README.md

&#x20; agent/

&#x20;   apertus\_agent.py

&#x20;   apertus\_client.py

&#x20; tools/

&#x20;   extract\_invoice.py

&#x20;   find\_purchase\_order.py

&#x20;   compare\_amounts.py

&#x20;   send\_alert.py

&#x20;   mark\_as\_approved.py

&#x20; templates/

&#x20;   chat.html

&#x20; static/

&#x20;   css/chat.css

&#x20;   js/chat.js



\## License



MIT License — see LICENSE file.



Copyright (c) 2026 Anio Joseph



\## Author



Anio Joseph — Built for Hack Apertus, October 2026.

