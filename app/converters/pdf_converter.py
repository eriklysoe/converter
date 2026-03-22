import os
import subprocess
import logging
from pathlib import Path

from PIL import Image
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

logger = logging.getLogger(__name__)


def pdf_to_images(input_path: str, temp_dir: str, uid: str, fmt: str) -> list[str]:
    """
    Render each PDF page to an image using Inkscape (high quality).
    Falls back to pdftoppm if available for speed on large files.
    Returns list of output file paths.
    """
    reader = PdfReader(input_path)
    page_count = len(reader.pages)
    outputs = []

    for i in range(page_count):
        out_path = os.path.join(temp_dir, f"{uid}_page{i+1}.{fmt}")

        # Split single page to a temp PDF, then rasterize with Inkscape
        single_pdf = os.path.join(temp_dir, f"{uid}_p{i+1}.pdf")
        writer = PdfWriter()
        writer.add_page(reader.pages[i])
        with open(single_pdf, "wb") as f:
            writer.write(f)

        # Inkscape only supports PNG export; convert to JPG via Pillow if needed
        if fmt in ("jpg", "jpeg"):
            png_path = os.path.join(temp_dir, f"{uid}_page{i+1}.png")
            cmd = [
                "inkscape", "--pdf-poppler", single_pdf,
                "--export-type=png", f"--export-filename={png_path}",
                "--export-dpi=300",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"Inkscape failed on page {i+1}: {result.stderr}")
            from PIL import Image
            Image.MAX_IMAGE_PIXELS = None
            with Image.open(png_path) as img:
                img.convert("RGB").save(out_path, "JPEG", quality=95)
            os.remove(png_path)
        else:
            cmd = [
                "inkscape", "--pdf-poppler", single_pdf,
                f"--export-type={fmt}", f"--export-filename={out_path}",
                "--export-dpi=300",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"Inkscape failed on page {i+1}: {result.stderr}")

        os.remove(single_pdf)
        outputs.append(out_path)
        logger.info("Rendered page %d/%d", i + 1, page_count)

    return outputs


def pdf_to_svg(input_path: str, temp_dir: str, uid: str) -> list[str]:
    """
    Convert each PDF page to a high-quality SVG using Inkscape with --pdf-poppler.
    Returns list of output SVG file paths.
    """
    reader = PdfReader(input_path)
    page_count = len(reader.pages)
    outputs = []

    for i in range(page_count):
        out_path = os.path.join(temp_dir, f"{uid}_page{i+1}.svg")

        # Write single-page PDF
        single_pdf = os.path.join(temp_dir, f"{uid}_p{i+1}.pdf")
        writer = PdfWriter()
        writer.add_page(reader.pages[i])
        with open(single_pdf, "wb") as f:
            writer.write(f)

        cmd = [
            "inkscape",
            "--pdf-poppler",
            single_pdf,
            "--export-type=svg",
            f"--export-filename={out_path}",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Inkscape SVG conversion failed on page {i+1}: {result.stderr}")

        os.remove(single_pdf)
        outputs.append(out_path)
        logger.info("Converted page %d/%d to SVG", i + 1, page_count)

    return outputs


def images_to_pdf(image_paths: list[str], output_path: str) -> None:
    """Combine one or more images into a single PDF using ReportLab."""
    c = None
    for idx, img_path in enumerate(image_paths):
        with Image.open(img_path) as img:
            width, height = img.size
            # Convert pixels to points (72 dpi → points)
            w_pt = width * 72 / 96
            h_pt = height * 72 / 96

            if idx == 0:
                c = canvas.Canvas(output_path, pagesize=(w_pt, h_pt))
            else:
                c.showPage()
                c.setPageSize((w_pt, h_pt))

            c.drawImage(ImageReader(img_path), 0, 0, width=w_pt, height=h_pt)

    if c:
        c.save()
    logger.info("Created PDF from %d image(s)", len(image_paths))


def merge_pdfs(input_paths: list[str], output_path: str) -> None:
    """Merge multiple PDF files into one."""
    writer = PdfWriter()
    for path in input_paths:
        reader = PdfReader(path)
        for page in reader.pages:
            writer.add_page(page)
    with open(output_path, "wb") as f:
        writer.write(f)
    logger.info("Merged %d PDFs", len(input_paths))
