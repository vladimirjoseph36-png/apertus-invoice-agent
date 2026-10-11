"""Unit tests for the OCR engine."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.ocr_engine import check_ocr_available, extract_text_from_file


def test_ocr_stack_available():
    """The OCR stack should report its availability."""
    status = check_ocr_available()
    assert "pytesseract" in status
    assert "pdf2image" in status
    assert "tesseract_cmd" in status


def test_extract_nonexistent_file():
    result = extract_text_from_file("does_not_exist.png")
    assert result["success"] is False
    assert "not found" in result["error"].lower()


def test_extract_unsupported_extension():
    # Use a real file that exists but with unsupported extension
    result = extract_text_from_file("requirements.txt")
    assert result["success"] is False