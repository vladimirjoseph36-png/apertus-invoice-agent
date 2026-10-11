#!/usr/bin/env bash
# ==============================================================
# Render build script - installs system + Python dependencies
# ==============================================================
set -o errexit

echo "=== Installing system dependencies ==="

# Tesseract OCR + 5 languages
apt-get update
apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-fra \
    tesseract-ocr-eng \
    tesseract-ocr-deu \
    tesseract-ocr-ita \
    tesseract-ocr-spa \
    poppler-utils

echo "=== Installing Python dependencies ==="
pip install --upgrade pip
pip install -r requirements.txt

echo "=== Initializing database ==="
python tools/init_database.py
python tools/migrate_analyses_table.py
python tools/migrate_po_table.py

echo "=== Build complete ==="