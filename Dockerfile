# ==============================================================
# Apertus Invoice Assistant - Dockerfile for Render
# ==============================================================
# Multi-stage build:
#   - Installs Tesseract OCR (5 languages) + Poppler for PDF
#   - Installs Python 3.11 + dependencies
#   - Runs FastAPI with uvicorn
# ==============================================================

FROM python:3.11-slim

# ---------- System dependencies ----------
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-fra \
    tesseract-ocr-eng \
    tesseract-ocr-deu \
    tesseract-ocr-ita \
    tesseract-ocr-spa \
    poppler-utils \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ---------- Environment ----------
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TESSDATA_PREFIX=/usr/share/tesseract-ocr/5/tessdata \
    DEBIAN_FRONTEND=noninteractive

# ---------- Working directory ----------
WORKDIR /app

# ---------- Python dependencies ----------
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ---------- Application code ----------
COPY . .

# ---------- Create data + uploads directories ----------
RUN mkdir -p /app/data /app/uploads && \
    python tools/init_database.py && \
    python tools/migrate_analyses_table.py && \
    python tools/migrate_po_table.py

# ---------- Expose port ----------
EXPOSE 8000

# ---------- Healthcheck ----------
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

# ---------- Run ----------
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]