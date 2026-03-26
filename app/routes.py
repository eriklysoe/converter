import os
import uuid
import logging
import zipfile
from functools import wraps
from flask import Blueprint, request, jsonify, send_file, render_template, current_app, Response
from werkzeug.utils import secure_filename

ADMIN_USER = os.environ.get("ADMIN_USER", "")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "")

from .converters.image_converter import convert_image
from .converters.pdf_converter import (
    pdf_to_images,
    pdf_to_svg,
    images_to_pdf,
    merge_pdfs,
)
from .converters.document_converter import (
    document_to_pdf, pdf_to_docx, pdf_to_odt, pdf_to_pptx,
    markdown_to_pdf, csv_to_xlsx, xlsx_to_csv,
)
from .converters.eps_converter import eps_to_image, eps_to_svg, eps_to_pdf, to_eps
from .converters.audio_converter import (
    audio_to_mp3_320, audio_to_mp3_vbr, audio_to_wav, audio_to_flac,
    audio_to_ogg, audio_to_aiff,
)
from .converters.video_converter import video_to_mp4, video_to_mp3, video_to_gif
from .converters.image_converter import convert_raw_to_image, convert_gif_webp

logger = logging.getLogger(__name__)
main = Blueprint("main", __name__)


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or auth.username != ADMIN_USER or auth.password != ADMIN_PASS:
            return Response("Login required.", 401,
                            {"WWW-Authenticate": 'Basic realm="Converter"'})
        return f(*args, **kwargs)
    return decorated

ALLOWED_EXTENSIONS = {
    "jpg", "jpeg", "png", "webp", "bmp", "tiff", "tif", "ico",
    "heic", "heif", "avif", "svg", "eps",
    "pdf", "docx", "doc", "odt", "pptx", "xlsx", "rtf",
    "flac", "wav", "mp3", "ogg", "m4a", "aac", "aiff",
    "mp4", "mkv", "mov",
    "md", "csv",
    "gif", "cr2", "nef", "arw"
}

CONVERSION_MAP = {
    "jpg":  ["png", "webp", "bmp", "tiff", "ico", "avif", "pdf", "eps"],
    "jpeg": ["png", "webp", "bmp", "tiff", "ico", "avif", "pdf", "eps"],
    "png":  ["jpg", "webp", "bmp", "tiff", "ico", "avif", "pdf", "eps"],
    "webp": ["jpg", "png", "bmp", "tiff", "ico", "avif", "pdf", "eps", "gif"],
    "bmp":  ["jpg", "png", "webp", "tiff", "ico", "avif", "pdf", "eps"],
    "tiff": ["jpg", "png", "webp", "bmp", "ico", "avif", "pdf", "eps"],
    "tif":  ["jpg", "png", "webp", "bmp", "ico", "avif", "pdf", "eps"],
    "ico":  ["jpg", "png", "webp", "bmp", "tiff", "avif"],
    "heic": ["jpg", "png", "webp", "bmp", "tiff", "avif", "pdf", "eps"],
    "heif": ["jpg", "png", "webp", "bmp", "tiff", "avif", "pdf", "eps"],
    "avif": ["jpg", "png", "webp", "bmp", "tiff", "ico", "pdf", "eps"],
    "svg":  ["png", "jpg", "eps"],
    "eps":  ["png", "jpg", "svg", "pdf"],
    "pdf":  ["png", "jpg", "svg", "docx", "odt", "pptx", "eps"],
    "docx": ["pdf"],
    "doc":  ["pdf"],
    "odt":  ["pdf"],
    "pptx": ["pdf"],
    "xlsx": ["pdf", "csv"],
    "rtf":  ["pdf"],
    "flac": ["mp3-320", "mp3-vbr", "wav", "ogg", "aiff"],
    "wav":  ["mp3-320", "mp3-vbr", "flac", "ogg", "aiff"],
    "mp3":  ["wav", "flac", "ogg", "aiff"],
    "ogg":  ["mp3-320", "mp3-vbr", "wav", "flac", "aiff"],
    "m4a":  ["mp3-320", "mp3-vbr", "wav", "flac", "ogg"],
    "aac":  ["mp3-320", "mp3-vbr", "wav", "flac", "ogg"],
    "aiff": ["mp3-320", "mp3-vbr", "wav", "flac", "ogg"],
    "mp4":  ["mp3", "gif"],
    "mkv":  ["mp4", "mp3", "gif"],
    "mov":  ["mp4", "mp3", "gif"],
    "md":   ["pdf"],
    "csv":  ["xlsx"],
    "gif":  ["webp", "png", "jpg"],
    "cr2":  ["jpg", "png"],
    "nef":  ["jpg", "png"],
    "arw":  ["jpg", "png"],
}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_ext(filename):
    return filename.rsplit(".", 1)[1].lower()


def temp_path(filename):
    return os.path.join(current_app.config["TEMP_DIR"], filename)


@main.route("/")
@require_auth
def index():
    return render_template("index.html")


@main.route("/api/formats", methods=["POST"])
@require_auth
def get_formats():
    """Return valid output formats based on filename extensions.
    Accepts {"filename": "..."} or {"filenames": [...]} and returns
    the intersection of supported targets across all files.
    """
    data = request.get_json(silent=True) or {}
    filenames = data.get("filenames") or []
    if not filenames and data.get("filename"):
        filenames = [data["filename"]]
    if not filenames:
        return jsonify({"error": "No filename provided"}), 400

    format_sets = []
    for fn in filenames:
        if "." not in fn:
            continue
        ext = get_ext(fn)
        targets = CONVERSION_MAP.get(ext, [])
        if targets:
            format_sets.append(set(targets))

    if not format_sets:
        return jsonify({"output_formats": []})

    common = format_sets[0]
    for s in format_sets[1:]:
        common &= s

    return jsonify({"output_formats": sorted(common)})


@main.route("/api/convert", methods=["POST"])
@require_auth
def convert():
    """Main conversion endpoint. Supports single or multiple files."""
    files = request.files.getlist("file")
    if not files:
        return jsonify({"error": "No file provided"}), 400

    target = request.form.get("target_format", "").lower()
    if not target:
        return jsonify({"error": "No target format specified"}), 400

    # Validate all files
    for f in files:
        if not f or not allowed_file(f.filename):
            return jsonify({"error": f"Unsupported file type: {f.filename}"}), 400
        src_ext = get_ext(f.filename)
        if target not in CONVERSION_MAP.get(src_ext, []):
            return jsonify({"error": f"Cannot convert {f.filename} to {target}"}), 400

    temp = current_app.config["TEMP_DIR"]
    merge = request.form.get("merge") == "1" and len(files) > 1
    input_paths = []
    output_paths = []

    try:
        # Save all uploads
        saved_files = []
        for f in files:
            uid = uuid.uuid4().hex
            safe_name = secure_filename(f.filename)
            input_path = temp_path(f"{uid}_{safe_name}")
            f.save(input_path)
            input_paths.append(input_path)
            saved_files.append((input_path, get_ext(f.filename), f.filename))
            logger.info("Received %s → %s (%s)", get_ext(f.filename), target, safe_name)

        # Merge mode: combine inputs into one PDF, then convert
        if merge:
            merge_uid = uuid.uuid4().hex

            # If all inputs are PDFs, merge directly; otherwise convert each to PDF first
            pdf_paths = []
            for inp, ext, orig in saved_files:
                if ext == "pdf":
                    pdf_paths.append(inp)
                else:
                    # Convert to PDF first
                    tmp_pdf = os.path.join(temp, f"{merge_uid}_{os.path.basename(inp)}.pdf")
                    tmp_out, _, _ = dispatch(inp, ext, "pdf", merge_uid + os.path.basename(inp))
                    pdf_paths.append(tmp_out)

            merged_pdf = os.path.join(temp, f"{merge_uid}_merged.pdf")
            merge_pdfs(pdf_paths, merged_pdf)
            input_paths.append(merged_pdf)

            if target == "pdf":
                return send_file(merged_pdf, mimetype="application/pdf",
                                 as_attachment=True, download_name="merged.pdf")

            out_path, mime, dl_name = dispatch(merged_pdf, "pdf", target, merge_uid)
            return send_file(out_path, mimetype=mime, as_attachment=True,
                             download_name=f"merged.{target}")

        # Normal mode: convert each file individually
        for inp, ext, orig in saved_files:
            uid = uuid.uuid4().hex
            out_path, mime, dl_name = dispatch(inp, ext, target, uid)
            output_paths.append((out_path, mime, dl_name, orig))

        # Single file — return directly
        if len(output_paths) == 1:
            out_path, mime, dl_name, orig = output_paths[0]
            return send_file(out_path, mimetype=mime, as_attachment=True, download_name=dl_name)

        # Multiple files — zip all outputs
        zip_uid = uuid.uuid4().hex
        zip_path = os.path.join(temp, f"{zip_uid}_batch.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            for out_path, mime, dl_name, orig_name in output_paths:
                base = os.path.splitext(orig_name)[0]
                if out_path.endswith(".zip"):
                    arc_name = f"{base}.zip"
                else:
                    arc_name = f"{base}.{target}"
                zf.write(out_path, arc_name)

        return send_file(zip_path, mimetype="application/zip", as_attachment=True, download_name="converted.zip")

    except Exception as e:
        logger.error("Conversion failed: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500
    finally:
        for p in input_paths:
            if os.path.exists(p):
                os.remove(p)


def dispatch(input_path, src_ext, target, uid):
    """Route conversion to the correct converter module."""
    temp = current_app.config["TEMP_DIR"]

    # EPS → image
    if src_ext == "eps" and target in ("png", "jpg"):
        out = os.path.join(temp, f"{uid}_out.{target}")
        eps_to_image(input_path, out, target)
        return out, f"image/{target}", f"converted.{target}"

    # EPS → SVG
    if src_ext == "eps" and target == "svg":
        out = os.path.join(temp, f"{uid}_out.svg")
        eps_to_svg(input_path, out)
        return out, "image/svg+xml", "converted.svg"

    # EPS → PDF
    if src_ext == "eps" and target == "pdf":
        out = os.path.join(temp, f"{uid}_out.pdf")
        eps_to_pdf(input_path, out)
        return out, "application/pdf", "converted.pdf"

    # Any → EPS (images, SVG, PDF)
    if target == "eps":
        out = os.path.join(temp, f"{uid}_out.eps")
        to_eps(input_path, out)
        return out, "application/postscript", "converted.eps"

    # SVG → raster (must use Inkscape, not Pillow)
    if src_ext == "svg" and target in ("png", "jpg", "jpeg"):
        out = os.path.join(temp, f"{uid}_out.{target}")
        png_out = os.path.join(temp, f"{uid}_out.png")
        import subprocess as _sp
        cmd = [
            "inkscape", input_path,
            "--export-type=png", f"--export-filename={png_out}",
            "--export-dpi=300",
        ]
        result = _sp.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Inkscape SVG→PNG failed: {result.stderr}")
        if target in ("jpg", "jpeg"):
            from PIL import Image as _Img
            _Img.MAX_IMAGE_PIXELS = None
            with _Img.open(png_out) as img:
                img.convert("RGB").save(out, "JPEG", quality=95)
            os.remove(png_out)
        else:
            os.rename(png_out, out)
        mime = f"image/{target}"
        return out, mime, f"converted.{target}"

    raster_inputs = ("jpg", "jpeg", "png", "webp", "bmp", "tiff", "tif", "ico", "heic", "heif", "avif")
    raster_targets = ("jpg", "jpeg", "png", "webp", "bmp", "tiff", "tif", "ico", "avif")

    # Image ↔ image (including TIFF, ICO, HEIC, AVIF)
    if src_ext in raster_inputs and target in raster_targets:
        out = os.path.join(temp, f"{uid}_out.{target}")
        convert_image(input_path, out, target)
        mime = {"tiff": "image/tiff", "tif": "image/tiff", "ico": "image/x-icon", "avif": "image/avif"}.get(target, f"image/{target}")
        return out, mime, f"converted.{target}"

    # Image → PDF
    if src_ext in raster_inputs and src_ext != "svg" and target == "pdf":
        out = os.path.join(temp, f"{uid}_out.pdf")
        images_to_pdf([input_path], out)
        return out, "application/pdf", "converted.pdf"

    # PDF → image
    if src_ext == "pdf" and target in ("jpg", "jpeg", "png"):
        pages = pdf_to_images(input_path, temp, uid, target)
        if len(pages) == 1:
            return pages[0], f"image/{target}", f"page1.{target}"
        # Multiple pages → zip
        zip_path = os.path.join(temp, f"{uid}_pages.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            for p in pages:
                zf.write(p, os.path.basename(p))
        return zip_path, "application/zip", "pages.zip"

    # PDF → SVG
    if src_ext == "pdf" and target == "svg":
        svgs = pdf_to_svg(input_path, temp, uid)
        if len(svgs) == 1:
            return svgs[0], "image/svg+xml", "converted.svg"
        zip_path = os.path.join(temp, f"{uid}_svgs.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            for s in svgs:
                zf.write(s, os.path.basename(s))
        return zip_path, "application/zip", "converted_svg.zip"

    # PDF → DOCX
    if src_ext == "pdf" and target == "docx":
        out = os.path.join(temp, f"{uid}_out.docx")
        pdf_to_docx(input_path, out)
        return out, "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "converted.docx"

    # PDF → ODT
    if src_ext == "pdf" and target == "odt":
        out = os.path.join(temp, f"{uid}_out.odt")
        pdf_to_odt(input_path, out, temp)
        return out, "application/vnd.oasis.opendocument.text", "converted.odt"

    # PDF → PPTX
    if src_ext == "pdf" and target == "pptx":
        out = os.path.join(temp, f"{uid}_out.pptx")
        pdf_to_pptx(input_path, out, temp)
        return out, "application/vnd.openxmlformats-officedocument.presentationml.presentation", "converted.pptx"

    # DOCX/DOC/ODT/PPTX/XLSX/RTF → PDF
    if src_ext in ("docx", "doc", "odt", "pptx", "xlsx", "rtf") and target == "pdf":
        out = os.path.join(temp, f"{uid}_out.pdf")
        document_to_pdf(input_path, out, temp)
        return out, "application/pdf", "converted.pdf"

    # ── Audio conversions ─────────────────────────────────────────
    audio_inputs = ("flac", "wav", "mp3", "ogg", "m4a", "aac", "aiff")

    if src_ext in audio_inputs and target == "mp3-320":
        out = os.path.join(temp, f"{uid}_out.mp3")
        audio_to_mp3_320(input_path, out)
        return out, "audio/mpeg", "converted.mp3"

    if src_ext in audio_inputs and target == "mp3-vbr":
        out = os.path.join(temp, f"{uid}_out.mp3")
        audio_to_mp3_vbr(input_path, out)
        return out, "audio/mpeg", "converted.mp3"

    if src_ext in audio_inputs and target == "wav":
        out = os.path.join(temp, f"{uid}_out.wav")
        audio_to_wav(input_path, out)
        return out, "audio/wav", "converted.wav"

    if src_ext in audio_inputs and target == "flac":
        out = os.path.join(temp, f"{uid}_out.flac")
        audio_to_flac(input_path, out)
        return out, "audio/flac", "converted.flac"

    if src_ext in audio_inputs and target == "ogg":
        out = os.path.join(temp, f"{uid}_out.ogg")
        audio_to_ogg(input_path, out)
        return out, "audio/ogg", "converted.ogg"

    if src_ext in audio_inputs and target == "aiff":
        out = os.path.join(temp, f"{uid}_out.aiff")
        audio_to_aiff(input_path, out)
        return out, "audio/aiff", "converted.aiff"

    # ── Video conversions ─────────────────────────────────────────
    video_inputs = ("mp4", "mkv", "mov")

    if src_ext in video_inputs and target == "mp4":
        out = os.path.join(temp, f"{uid}_out.mp4")
        video_to_mp4(input_path, out)
        return out, "video/mp4", "converted.mp4"

    if src_ext in video_inputs and target == "mp3":
        out = os.path.join(temp, f"{uid}_out.mp3")
        video_to_mp3(input_path, out)
        return out, "audio/mpeg", "converted.mp3"

    if src_ext in video_inputs and target == "gif":
        out = os.path.join(temp, f"{uid}_out.gif")
        video_to_gif(input_path, out)
        return out, "image/gif", "converted.gif"

    # ── Markdown → PDF ────────────────────────────────────────────
    if src_ext == "md" and target == "pdf":
        out = os.path.join(temp, f"{uid}_out.pdf")
        markdown_to_pdf(input_path, out)
        return out, "application/pdf", "converted.pdf"

    # ── CSV → XLSX ────────────────────────────────────────────────
    if src_ext == "csv" and target == "xlsx":
        out = os.path.join(temp, f"{uid}_out.xlsx")
        csv_to_xlsx(input_path, out)
        return out, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "converted.xlsx"

    # ── XLSX → CSV ────────────────────────────────────────────────
    if src_ext == "xlsx" and target == "csv":
        out = os.path.join(temp, f"{uid}_out.csv")
        xlsx_to_csv(input_path, out)
        return out, "text/csv", "converted.csv"

    # ── GIF ↔ WebP (animated-aware) ──────────────────────────────
    if src_ext == "gif" and target == "webp":
        out = os.path.join(temp, f"{uid}_out.webp")
        convert_gif_webp(input_path, out, "webp")
        return out, "image/webp", "converted.webp"

    if src_ext == "webp" and target == "gif":
        out = os.path.join(temp, f"{uid}_out.gif")
        convert_gif_webp(input_path, out, "gif")
        return out, "image/gif", "converted.gif"

    # ── GIF → raster (PNG/JPG via Pillow) ─────────────────────────
    if src_ext == "gif" and target in ("png", "jpg"):
        out = os.path.join(temp, f"{uid}_out.{target}")
        convert_image(input_path, out, target)
        mime = {"png": "image/png", "jpg": "image/jpeg"}[target]
        return out, mime, f"converted.{target}"

    # ── RAW → JPG/PNG ─────────────────────────────────────────────
    if src_ext in ("cr2", "nef", "arw") and target in ("jpg", "png"):
        out = os.path.join(temp, f"{uid}_out.{target}")
        convert_raw_to_image(input_path, out, target)
        return out, f"image/{target}", f"converted.{target}"

    raise ValueError(f"No handler for {src_ext} → {target}")
