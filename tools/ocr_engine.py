"""
OCR engine for extracting text from images and PDFs.

Auto-detects the local tessdata folder and configures TESSDATA_PREFIX.
Auto-detects Poppler for PDF processing.

Supports: JPEG, PNG, TIFF, BMP, WEBP, PDF
Languages: French, English, German, Italian, Spanish

Author: Anio Joseph
Project: Hack Apertus - October 2026
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

# --- Configuration Tesseract ---

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOCAL_TESSDATA = PROJECT_ROOT / "tessdata"

# Set TESSDATA_PREFIX to point to the local tessdata folder
if LOCAL_TESSDATA.exists():
    os.environ["TESSDATA_PREFIX"] = str(LOCAL_TESSDATA)

# Auto-detect Tesseract binary path on Windows
if os.name == "nt":
    default_paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]
    for p in default_paths:
        if os.path.exists(p):
            os.environ.setdefault("TESSERACT_CMD", p)
            break


# --- Configuration Poppler (for PDF to image conversion) ---

if os.name == "nt":
    LOCAL_POPPLER = PROJECT_ROOT / "poppler" / "Library" / "bin"
    if LOCAL_POPPLER.exists():
        os.environ["POPPLER_PATH"] = str(LOCAL_POPPLER)
        print(f"[OCR] Poppler found locally: {LOCAL_POPPLER}")
    else:
        common_paths = [
            Path(r"C:\Program Files\poppler\Library\bin"),
            Path(r"C:\poppler\Library\bin"),
            Path(r"C:\Program Files (x86)\poppler\Library\bin"),
        ]
        for p in common_paths:
            if p.exists():
                os.environ["POPPLER_PATH"] = str(p)
                print(f"[OCR] Poppler found at: {p}")
                break
        else:
            print("[OCR] WARNING: Poppler not found.")
            print("[OCR] Install Poppler in ./poppler/Library/bin/ for PDF support.")


try:
    import pytesseract
    from PIL import Image
    if os.environ.get("TESSERACT_CMD"):
        pytesseract.pytesseract.tesseract_cmd = os.environ["TESSERACT_CMD"]
    PYTESSERACT_AVAILABLE = True
except ImportError:
    PYTESSERACT_AVAILABLE = False
    print("[WARNING] pytesseract not installed. OCR disabled.")

try:
    from pdf2image import convert_from_path
    PDF2IMAGE_AVAILABLE = True
except ImportError:
    PDF2IMAGE_AVAILABLE = False
    print("[WARNING] pdf2image not installed. PDF OCR disabled.")


SUPPORTED_LANGS = "fra+eng+deu+ita+spa"
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp"}
PDF_EXTS = {".pdf"}


def ocr_image(image_path: str, lang: str = SUPPORTED_LANGS) -> Dict[str, Any]:
    """Extract text from an image file using OCR."""
    if not PYTESSERACT_AVAILABLE:
        return {"success": False, "text": "", "error": "pytesseract not available"}

    path = Path(image_path)
    if not path.exists():
        return {"success": False, "text": "", "error": f"file not found: {image_path}"}

    try:
        img = Image.open(image_path)
        text = pytesseract.image_to_string(img, lang=lang)
        return {
            "success": True,
            "text": text.strip(),
            "error": None,
            "source": str(path),
            "lang": lang,
        }
    except Exception as e:
        return {"success": False, "text": "", "error": f"{type(e).__name__}: {e}"}


def ocr_pdf(pdf_path: str, lang: str = SUPPORTED_LANGS, max_pages: int = 5) -> Dict[str, Any]:
    """Extract text from a PDF file using OCR."""
    if not PDF2IMAGE_AVAILABLE or not PYTESSERACT_AVAILABLE:
        return {"success": False, "text": "", "error": "pdf2image or pytesseract not available"}

    path = Path(pdf_path)
    if not path.exists():
        return {"success": False, "text": "", "error": f"file not found: {pdf_path}"}

    try:
        poppler_path = os.environ.get("POPPLER_PATH")
        if poppler_path:
            pages = convert_from_path(
                pdf_path,
                dpi=200,
                first_page=1,
                last_page=max_pages,
                poppler_path=poppler_path,
            )
        else:
            pages = convert_from_path(pdf_path, dpi=200, first_page=1, last_page=max_pages)

        full_text = []
        for i, page_img in enumerate(pages, 1):
            page_text = pytesseract.image_to_string(page_img, lang=lang)
            full_text.append(f"--- Page {i} ---\n{page_text.strip()}")

        return {
            "success": True,
            "text": "\n\n".join(full_text),
            "error": None,
            "source": str(path),
            "lang": lang,
            "pages": len(pages),
        }
    except Exception as e:
        return {"success": False, "text": "", "error": f"{type(e).__name__}: {e}"}


def extract_text_from_file(file_path: str, lang: str = SUPPORTED_LANGS) -> Dict[str, Any]:
    """
    Auto-detect file type and extract text via OCR.

    Supports: .jpg, .jpeg, .png, .tif, .tiff, .bmp, .webp, .pdf
    """
    path = Path(file_path)
    if not path.exists():
        return {"success": False, "text": "", "error": f"file not found: {file_path}"}

    ext = path.suffix.lower()

    if ext in IMAGE_EXTS:
        return ocr_image(file_path, lang=lang)

    if ext in PDF_EXTS:
        return ocr_pdf(file_path, lang=lang)

    return {"success": False, "text": "", "error": f"unsupported file type: {ext}"}


def check_ocr_available() -> Dict[str, Any]:
    """Check if OCR stack is properly installed."""
    status = {
        "pytesseract": PYTESSERACT_AVAILABLE,
        "pdf2image": PDF2IMAGE_AVAILABLE,
        "tesseract_cmd": os.environ.get("TESSERACT_CMD", "not set"),
        "tessdata_prefix": os.environ.get("TESSDATA_PREFIX", "not set"),
        "poppler_path": os.environ.get("POPPLER_PATH", "not set"),
    }

    if PYTESSERACT_AVAILABLE:
        try:
            version = pytesseract.get_tesseract_version()
            status["tesseract_version"] = str(version)
        except Exception as e:
            status["tesseract_error"] = str(e)

    return status


if __name__ == "__main__":
    print("=== OCR Stack Status ===")
    status = check_ocr_available()
    for k, v in status.items():
        print(f"  {k}: {v}")

    if PYTESSERACT_AVAILABLE:
        try:
            langs = pytesseract.get_languages()
            print(f"\n=== Installed Languages ===")
            print(f"  {langs}")
        except Exception as e:
            print(f"\n[ERROR] Cannot list languages: {e}")