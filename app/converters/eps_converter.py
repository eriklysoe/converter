import os
import subprocess
import logging

logger = logging.getLogger(__name__)


def eps_to_image(input_path: str, output_path: str, fmt: str) -> None:
    """Convert EPS to raster image via Ghostscript (EPS→PDF) then Inkscape (PDF→PNG) then Pillow."""
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None

    temp_pdf = output_path + ".tmp.pdf"
    try:
        # EPS → PDF via Ghostscript
        _eps_to_pdf_gs(input_path, temp_pdf)

        # PDF → PNG via Inkscape
        temp_png = output_path + ".tmp.png"
        cmd = [
            "inkscape", "--pdf-poppler", temp_pdf,
            "--export-type=png", f"--export-filename={temp_png}",
            "--export-dpi=300",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Inkscape PDF→PNG failed: {result.stderr}")

        # Convert to target format via Pillow if needed
        if fmt in ("jpg", "jpeg"):
            with Image.open(temp_png) as img:
                img.convert("RGB").save(output_path, "JPEG", quality=95)
            os.remove(temp_png)
        elif fmt == "png":
            os.rename(temp_png, output_path)
        else:
            with Image.open(temp_png) as img:
                img.save(output_path)
            os.remove(temp_png)
    finally:
        if os.path.exists(temp_pdf):
            os.remove(temp_pdf)

    logger.info("Converted EPS to %s", fmt)


def eps_to_svg(input_path: str, output_path: str) -> None:
    """Convert EPS to SVG: EPS→PDF (Ghostscript) then PDF→SVG (Inkscape)."""
    temp_pdf = output_path + ".tmp.pdf"
    try:
        _eps_to_pdf_gs(input_path, temp_pdf)
        cmd = [
            "inkscape", "--pdf-poppler", temp_pdf,
            "--export-type=svg", f"--export-filename={output_path}",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Inkscape PDF→SVG failed: {result.stderr}")
    finally:
        if os.path.exists(temp_pdf):
            os.remove(temp_pdf)
    logger.info("Converted EPS to SVG")


def eps_to_pdf(input_path: str, output_path: str) -> None:
    """Convert EPS to PDF using Ghostscript."""
    _eps_to_pdf_gs(input_path, output_path)
    logger.info("Converted EPS to PDF")


def to_eps(input_path: str, output_path: str) -> None:
    """Convert any supported format to EPS using Ghostscript (via PDF intermediate)."""
    ext = os.path.splitext(input_path)[1].lower()

    # If already PDF, convert directly
    if ext == ".pdf":
        _pdf_to_eps_gs(input_path, output_path)
    elif ext in (".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp"):
        # Raster → PDF via ReportLab, then PDF → EPS via Ghostscript
        from .pdf_converter import images_to_pdf
        temp_pdf = output_path + ".tmp.pdf"
        try:
            images_to_pdf([input_path], temp_pdf)
            _pdf_to_eps_gs(temp_pdf, output_path)
        finally:
            if os.path.exists(temp_pdf):
                os.remove(temp_pdf)
    elif ext == ".svg":
        # SVG → PDF via Inkscape, then PDF → EPS via Ghostscript
        temp_pdf = output_path + ".tmp.pdf"
        try:
            cmd = [
                "inkscape", input_path,
                "--export-type=pdf", f"--export-filename={temp_pdf}",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"Inkscape SVG→PDF failed: {result.stderr}")
            _pdf_to_eps_gs(temp_pdf, output_path)
        finally:
            if os.path.exists(temp_pdf):
                os.remove(temp_pdf)
    else:
        raise ValueError(f"Cannot convert {ext} to EPS")

    logger.info("Converted to EPS")


def _eps_to_pdf_gs(input_path: str, output_path: str) -> None:
    """Convert EPS to PDF using Ghostscript."""
    cmd = [
        "gs", "-q", "-dNOPAUSE", "-dBATCH", "-dSAFER",
        "-sDEVICE=pdfwrite",
        "-dEPSCrop",
        f"-sOutputFile={output_path}",
        input_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Ghostscript EPS→PDF failed: {result.stderr}")


def _pdf_to_eps_gs(input_path: str, output_path: str) -> None:
    """Convert PDF to EPS using Ghostscript."""
    cmd = [
        "gs", "-q", "-dNOPAUSE", "-dBATCH", "-dSAFER",
        "-sDEVICE=eps2write",
        f"-sOutputFile={output_path}",
        input_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Ghostscript PDF→EPS failed: {result.stderr}")
