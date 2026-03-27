import os
import subprocess
import logging

logger = logging.getLogger(__name__)


def pdf_to_ocr_pdf(input_path: str, output_path: str) -> None:
    """Add an OCR text layer to a PDF using ocrmypdf."""
    cmd = [
        "ocrmypdf",
        "--skip-text",       # Don't re-OCR pages that already have text
        "--output-type", "pdf",
        input_path, output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode not in (0, 6):  # 6 = already has text (skip-text mode)
        raise RuntimeError(f"ocrmypdf failed: {result.stderr}")
    logger.info("OCR added to PDF: %s", output_path)


def image_to_ocr_pdf(input_path: str, output_path: str) -> None:
    """Convert an image to a searchable PDF using ocrmypdf."""
    cmd = [
        "ocrmypdf",
        "--image-dpi", "300",
        input_path, output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ocrmypdf image→PDF failed: {result.stderr}")
    logger.info("Converted image to OCR PDF: %s", output_path)


def pdf_to_txt(input_path: str, output_path: str) -> None:
    """Extract text from a PDF using pdftotext (poppler-utils)."""
    cmd = ["pdftotext", "-layout", input_path, output_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"pdftotext failed: {result.stderr}")
    logger.info("Extracted text from PDF: %s", output_path)


def image_to_txt(input_path: str, output_path: str) -> None:
    """Extract text from an image using Tesseract OCR."""
    # Tesseract writes to output_base.txt, so strip the .txt extension
    output_base = output_path[:-4] if output_path.endswith(".txt") else output_path
    cmd = ["tesseract", input_path, output_base]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"tesseract failed: {result.stderr}")
    logger.info("Extracted text from image: %s.txt", output_base)
