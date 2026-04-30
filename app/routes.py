import os
import uuid
import logging
import time
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
    markdown_to_pdf, csv_to_xlsx, xlsx_to_csv, pdf_to_pdfa,
)
from .converters.eps_converter import eps_to_image, eps_to_svg, eps_to_pdf, to_eps
from .converters.audio_converter import (
    audio_to_mp3_cbr, audio_to_mp3_vbr, audio_to_wav, audio_to_flac,
    audio_to_ogg, audio_to_aiff, audio_to_m4a,
    audio_to_m4b_copy, audio_to_m4b_aac,
    split_by_chapters, split_by_size, get_input_bitrate_kbps,
)
from .converters.video_converter import (
    video_to_mp4, video_to_mp3, video_to_gif,
    video_to_webm, video_to_mp4_720p, video_to_mp4_1080p,
)
from .converters.ocr_converter import (
    pdf_to_ocr_pdf, image_to_ocr_pdf, pdf_to_txt, image_to_txt,
)
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
    "flac", "wav", "mp3", "ogg", "m4a", "m4b", "aac", "aiff",
    "mp4", "mkv", "mov", "webm",
    "md", "csv",
    "gif", "cr2", "nef", "arw",
    "zip",
}

CONVERSION_MAP = {
    "jpg":  ["png", "webp", "bmp", "tiff", "ico", "avif", "pdf", "eps", "ocr-pdf", "txt"],
    "jpeg": ["png", "webp", "bmp", "tiff", "ico", "avif", "pdf", "eps", "ocr-pdf", "txt"],
    "png":  ["jpg", "webp", "bmp", "tiff", "ico", "avif", "pdf", "eps", "ocr-pdf", "txt"],
    "webp": ["jpg", "png", "bmp", "tiff", "ico", "avif", "pdf", "eps", "gif", "ocr-pdf", "txt"],
    "bmp":  ["jpg", "png", "webp", "tiff", "ico", "avif", "pdf", "eps", "ocr-pdf", "txt"],
    "tiff": ["jpg", "png", "webp", "bmp", "ico", "avif", "pdf", "eps", "ocr-pdf", "txt"],
    "tif":  ["jpg", "png", "webp", "bmp", "ico", "avif", "pdf", "eps", "ocr-pdf", "txt"],
    "ico":  ["jpg", "png", "webp", "bmp", "tiff", "avif"],
    "heic": ["jpg", "png", "webp", "bmp", "tiff", "avif", "pdf", "eps", "ocr-pdf", "txt"],
    "heif": ["jpg", "png", "webp", "bmp", "tiff", "avif", "pdf", "eps", "ocr-pdf", "txt"],
    "avif": ["jpg", "png", "webp", "bmp", "tiff", "ico", "pdf", "eps", "ocr-pdf", "txt"],
    "svg":  ["png", "jpg", "eps", "pdf"],
    "eps":  ["png", "jpg", "svg", "pdf"],
    "pdf":  ["png", "jpg", "svg", "docx", "odt", "pptx", "eps", "pdf-a", "ocr-pdf", "txt"],
    "docx": ["pdf"],
    "doc":  ["pdf"],
    "odt":  ["pdf"],
    "pptx": ["pdf"],
    "xlsx": ["pdf", "csv"],
    "rtf":  ["pdf"],
    "flac": ["mp3-64", "mp3-96", "mp3-128", "mp3-192", "mp3-256", "mp3-320", "mp3-vbr", "wav", "ogg", "aiff", "m4a"],
    "wav":  ["mp3-64", "mp3-96", "mp3-128", "mp3-192", "mp3-256", "mp3-320", "mp3-vbr", "flac", "ogg", "aiff", "m4a"],
    "mp3":  ["wav", "flac", "ogg", "aiff", "m4a"],
    "ogg":  ["mp3-64", "mp3-96", "mp3-128", "mp3-192", "mp3-256", "mp3-320", "mp3-vbr", "wav", "flac", "aiff", "m4a"],
    "m4a":  ["mp3-64", "mp3-96", "mp3-128", "mp3-192", "mp3-256", "mp3-320", "mp3-vbr", "wav", "flac", "ogg"],
    "m4b":  ["mp3-64", "mp3-96", "mp3-128", "mp3-192", "mp3-256", "mp3-320", "mp3-vbr", "wav", "flac", "ogg", "m4a",
             "m4b", "m4b-64", "m4b-96", "m4b-128", "m4b-192", "m4b-256"],
    "aac":  ["mp3-64", "mp3-96", "mp3-128", "mp3-192", "mp3-256", "mp3-320", "mp3-vbr", "wav", "flac", "ogg", "m4a"],
    "aiff": ["mp3-64", "mp3-96", "mp3-128", "mp3-192", "mp3-256", "mp3-320", "mp3-vbr", "wav", "flac", "ogg", "m4a"],
    "mp4":  ["mp3", "gif", "webm", "mp4-720p", "mp4-1080p"],
    "mkv":  ["mp4", "mp3", "gif", "webm", "mp4-720p", "mp4-1080p"],
    "mov":  ["mp4", "mp3", "gif", "webm", "mp4-720p", "mp4-1080p"],
    "webm": ["mp4", "mp3", "gif", "mp4-720p", "mp4-1080p"],
    "md":   ["pdf"],
    "csv":  ["xlsx", "pdf"],
    "gif":  ["webp", "png", "jpg"],
    "cr2":  ["jpg", "png"],
    "nef":  ["jpg", "png"],
    "arw":  ["jpg", "png"],
    "zip":  ["jpg", "png", "webp", "pdf"],
}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_ext(filename):
    return filename.rsplit(".", 1)[1].lower()


def temp_path(filename):
    return os.path.join(current_app.config["TEMP_DIR"], filename)


def cleanup_files(paths):
    """Best-effort cleanup for temporary files."""
    seen = set()
    for path in paths:
        if not path or path in seen:
            continue
        seen.add(path)
        try:
            os.remove(path)
        except FileNotFoundError:
            continue
        except Exception as err:
            logger.warning("Failed to remove temp file %s: %s", path, err)


def send_file_with_cleanup(path, mimetype, download_name, cleanup_paths):
    """Return send_file response and clean temp files when response closes."""
    response = send_file(path, mimetype=mimetype, as_attachment=True, download_name=download_name)
    cleanup_snapshot = tuple(cleanup_paths)
    response.call_on_close(lambda: cleanup_files(cleanup_snapshot))
    return response


def user_error_message(exc):
    msg = str(exc).strip() or exc.__class__.__name__
    lowered = msg.lower()
    if "timeout" in lowered or "timed out" in lowered:
        return (
            "Conversion timed out before completion. "
            "Try splitting the file or increasing reverse-proxy timeouts."
        )
    return msg


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
    try:
        split_chapters = int(request.form.get("split_chapters", "0") or "0")
    except ValueError:
        split_chapters = 0
    try:
        split_size_mb = int(request.form.get("split_size_mb", "0") or "0")
    except ValueError:
        split_size_mb = 0
    if (split_chapters or split_size_mb) and (len(files) != 1 or get_ext(files[0].filename) != "m4b"):
        return jsonify({"error": "Split is only supported for a single m4b file"}), 400
    if split_chapters and split_size_mb:
        return jsonify({"error": "Choose either split-by-chapters or split-by-size, not both"}), 400
    request_id = uuid.uuid4().hex[:8]
    started = time.monotonic()
    cleanup_paths = []
    output_paths = []

    logger.info(
        "[%s] Convert start: files=%d target=%s merge=%s split_chapters=%d split_size_mb=%d",
        request_id, len(files), target, merge, split_chapters, split_size_mb
    )

    def _send_result(path, mimetype, download_name):
        cleanup_paths.append(path)
        elapsed = time.monotonic() - started
        try:
            out_bytes = os.path.getsize(path)
            logger.info(
                "[%s] Convert done in %.2fs: %s (%d bytes)",
                request_id, elapsed, download_name, out_bytes
            )
        except OSError:
            logger.info("[%s] Convert done in %.2fs: %s", request_id, elapsed, download_name)
        return send_file_with_cleanup(path, mimetype, download_name, cleanup_paths)

    try:
        # Save all uploads
        saved_files = []
        total_upload_bytes = 0
        for f in files:
            uid = uuid.uuid4().hex
            safe_name = secure_filename(f.filename)
            input_path = temp_path(f"{uid}_{safe_name}")
            f.save(input_path)
            cleanup_paths.append(input_path)

            try:
                total_upload_bytes += os.path.getsize(input_path)
            except OSError:
                pass

            src_ext = get_ext(f.filename)

            # ZIP input: extract and treat each file inside as an individual input
            if src_ext == "zip":
                with zipfile.ZipFile(input_path, "r") as zf:
                    for member in zf.namelist():
                        if member.endswith("/") or not allowed_file(member):
                            continue
                        member_ext = get_ext(member)
                        if target not in CONVERSION_MAP.get(member_ext, []):
                            continue
                        member_uid = uuid.uuid4().hex
                        member_safe = secure_filename(os.path.basename(member))
                        member_path = temp_path(f"{member_uid}_{member_safe}")
                        with zf.open(member) as src, open(member_path, "wb") as dst:
                            dst.write(src.read())
                        cleanup_paths.append(member_path)
                        saved_files.append((member_path, member_ext, os.path.basename(member)))
                continue

            saved_files.append((input_path, src_ext, f.filename))

        if not saved_files:
            cleanup_files(cleanup_paths)
            return jsonify({"error": "ZIP contained no files compatible with the selected target format"}), 400

        logger.info(
            "[%s] Accepted %d source item(s), upload size=%.2f MB",
            request_id, len(saved_files), total_upload_bytes / (1024 * 1024)
        )

        # Merge mode: combine inputs into one PDF, then convert
        if merge:
            merge_uid = uuid.uuid4().hex

            # If all inputs are PDFs, merge directly; otherwise convert each to PDF first
            pdf_paths = []
            for inp, ext, _orig in saved_files:
                if ext == "pdf":
                    pdf_paths.append(inp)
                else:
                    tmp_out, _, _ = dispatch(inp, ext, "pdf", merge_uid + os.path.basename(inp))
                    cleanup_paths.append(tmp_out)
                    pdf_paths.append(tmp_out)

            merged_pdf = os.path.join(temp, f"{merge_uid}_merged.pdf")
            merge_pdfs(pdf_paths, merged_pdf)
            cleanup_paths.append(merged_pdf)

            if target == "pdf":
                return _send_result(merged_pdf, "application/pdf", "merged.pdf")

            out_path, mime, _dl_name = dispatch(merged_pdf, "pdf", target, merge_uid)
            return _send_result(out_path, mime, f"merged.{target}")

        # Normal mode: convert each file individually
        for inp, ext, orig in saved_files:
            uid = uuid.uuid4().hex
            out_path, mime, dl_name = dispatch(
                inp, ext, target, uid,
                split_chapters=split_chapters,
                split_size_mb=split_size_mb,
                orig_name=orig,
            )
            output_paths.append((out_path, mime, dl_name, orig))

        # Single file — return directly
        if len(output_paths) == 1:
            out_path, mime, dl_name, _orig = output_paths[0]
            return _send_result(out_path, mime, dl_name)

        # Multiple files — zip all outputs
        zip_uid = uuid.uuid4().hex
        zip_path = os.path.join(temp, f"{zip_uid}_batch.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            for out_path, _mime, _dl_name, orig_name in output_paths:
                cleanup_paths.append(out_path)
                base = os.path.splitext(orig_name)[0]
                if out_path.endswith(".zip"):
                    arc_name = f"{base}.zip"
                else:
                    arc_name = f"{base}.{target}"
                zf.write(out_path, arc_name)

        return _send_result(zip_path, "application/zip", "converted.zip")

    except Exception as e:
        cleanup_files(cleanup_paths)
        elapsed = time.monotonic() - started
        logger.error("[%s] Conversion failed after %.2fs: %s", request_id, elapsed, e, exc_info=True)
        return jsonify({"error": user_error_message(e)}), 500


def _ffmpeg_args_for_audio_target(target):
    """Return (ffmpeg_args, output_ext, mime) for an audio target token."""
    if target == "mp3-vbr":
        return ["-map", "0:a", "-codec:a", "libmp3lame", "-q:a", "0"], "mp3", "audio/mpeg"
    if target.startswith("mp3-"):
        return (["-map", "0:a", "-codec:a", "libmp3lame", "-b:a", f"{int(target.rsplit('-', 1)[1])}k"],
                "mp3", "audio/mpeg")
    if target == "m4b":
        return (["-map", "0:a", "-map", "0:v?", "-c", "copy", "-f", "ipod"],
                "m4b", "audio/mp4")
    if target.startswith("m4b-"):
        return (["-map", "0:a", "-map", "0:v?",
                 "-c:a", "aac", "-b:a", f"{int(target.rsplit('-', 1)[1])}k",
                 "-c:v", "copy", "-f", "ipod"],
                "m4b", "audio/mp4")
    if target == "m4a":
        return ["-map", "0:a", "-codec:a", "aac", "-b:a", "256k"], "m4a", "audio/mp4"
    if target == "wav":
        return ["-map", "0:a", "-codec:a", "pcm_s24le"], "wav", "audio/wav"
    if target == "flac":
        return ["-map", "0:a", "-codec:a", "flac", "-compression_level", "8"], "flac", "audio/flac"
    if target == "ogg":
        return ["-map", "0:a", "-codec:a", "libvorbis", "-q:a", "6"], "ogg", "audio/ogg"
    if target == "aiff":
        return ["-map", "0:a", "-codec:a", "pcm_s16be"], "aiff", "audio/aiff"
    raise ValueError(f"Unsupported audio target for split: {target}")


def _estimated_output_bitrate_kbps(target, input_path):
    """Best-effort estimate of output audio bitrate (kbps) for size budgeting."""
    if target.startswith("mp3-") and target != "mp3-vbr":
        return int(target.rsplit("-", 1)[1])
    if target == "mp3-vbr":
        return 245  # LAME V0
    if target.startswith("m4b-"):
        return int(target.rsplit("-", 1)[1])
    if target == "m4b":
        return get_input_bitrate_kbps(input_path)  # stream copy
    if target == "m4a":
        return 256
    if target == "ogg":
        return 192
    if target == "aiff":
        # 16-bit stereo @ 44.1kHz ≈ 1411 kbps
        return 1411
    if target == "wav":
        # 24-bit stereo @ 44.1kHz ≈ 2116 kbps
        return 2116
    if target == "flac":
        # FLAC ~50-60% of WAV; conservative estimate
        return 1000
    return get_input_bitrate_kbps(input_path)


def dispatch(input_path, src_ext, target, uid, split_chapters=0, split_size_mb=0, orig_name=None):
    """Route conversion to the correct converter module."""
    temp = current_app.config["TEMP_DIR"]

    # Stem of original filename, used to name parts inside split ZIPs.
    arc_stem = os.path.splitext(secure_filename(orig_name or "split"))[0] or "split"

    # ── m4b chapter-split (with or without re-encode) ─────────────
    if src_ext == "m4b" and split_chapters >= 2:
        args, out_ext, _mime = _ffmpeg_args_for_audio_target(target)
        parts = split_by_chapters(input_path, temp, f"{uid}_split",
                                  split_chapters, args, out_ext)
        zip_path = os.path.join(temp, f"{uid}_split.zip")
        try:
            with zipfile.ZipFile(zip_path, "w") as zf:
                for i, p in enumerate(parts, 1):
                    zf.write(p, f"{arc_stem}_part_{i:02d}.{out_ext}")
        finally:
            cleanup_files(parts)
        return zip_path, "application/zip", f"{arc_stem}_split.zip"

    # ── m4b size-split (with or without re-encode) ────────────────
    if src_ext == "m4b" and split_size_mb >= 1:
        args, out_ext, _mime = _ffmpeg_args_for_audio_target(target)
        est_kbps = _estimated_output_bitrate_kbps(target, input_path)
        parts = split_by_size(input_path, temp, f"{uid}_split",
                              split_size_mb, args, out_ext, est_kbps)
        zip_path = os.path.join(temp, f"{uid}_split.zip")
        try:
            with zipfile.ZipFile(zip_path, "w") as zf:
                for i, p in enumerate(parts, 1):
                    zf.write(p, f"{arc_stem}_part_{i:02d}.{out_ext}")
        finally:
            cleanup_files(parts)
        return zip_path, "application/zip", f"{arc_stem}_split.zip"

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

    # SVG → PDF
    if src_ext == "svg" and target == "pdf":
        out = os.path.join(temp, f"{uid}_out.pdf")
        import subprocess as _sp
        cmd = ["inkscape", input_path, "--export-type=pdf", f"--export-filename={out}"]
        result = _sp.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Inkscape SVG→PDF failed: {result.stderr}")
        return out, "application/pdf", "converted.pdf"

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
        try:
            with zipfile.ZipFile(zip_path, "w") as zf:
                for p in pages:
                    zf.write(p, os.path.basename(p))
        finally:
            cleanup_files(pages)
        return zip_path, "application/zip", "pages.zip"

    # PDF → SVG
    if src_ext == "pdf" and target == "svg":
        svgs = pdf_to_svg(input_path, temp, uid)
        if len(svgs) == 1:
            return svgs[0], "image/svg+xml", "converted.svg"
        zip_path = os.path.join(temp, f"{uid}_svgs.zip")
        try:
            with zipfile.ZipFile(zip_path, "w") as zf:
                for s in svgs:
                    zf.write(s, os.path.basename(s))
        finally:
            cleanup_files(svgs)
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

    # DOCX/DOC/ODT/PPTX/XLSX/CSV/RTF → PDF
    if src_ext in ("docx", "doc", "odt", "pptx", "xlsx", "csv", "rtf") and target == "pdf":
        out = os.path.join(temp, f"{uid}_out.pdf")
        document_to_pdf(input_path, out, temp)
        return out, "application/pdf", "converted.pdf"

    # ── Audio conversions ─────────────────────────────────────────
    audio_inputs = ("flac", "wav", "mp3", "ogg", "m4a", "m4b", "aac", "aiff")
    mp3_cbr_bitrates = {
        "mp3-64": 64, "mp3-96": 96, "mp3-128": 128,
        "mp3-192": 192, "mp3-256": 256, "mp3-320": 320,
    }

    if src_ext in audio_inputs and target in mp3_cbr_bitrates:
        out = os.path.join(temp, f"{uid}_out.mp3")
        audio_to_mp3_cbr(input_path, out, mp3_cbr_bitrates[target])
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

    if src_ext in audio_inputs and target == "m4a":
        out = os.path.join(temp, f"{uid}_out.m4a")
        audio_to_m4a(input_path, out)
        return out, "audio/mp4", "converted.m4a"

    if src_ext == "m4b" and target == "m4b":
        out = os.path.join(temp, f"{uid}_out.m4b")
        audio_to_m4b_copy(input_path, out)
        return out, "audio/mp4", "converted.m4b"

    if src_ext == "m4b" and target.startswith("m4b-"):
        bitrate = int(target.rsplit("-", 1)[1])
        out = os.path.join(temp, f"{uid}_out.m4b")
        audio_to_m4b_aac(input_path, out, bitrate)
        return out, "audio/mp4", "converted.m4b"

    # ── Video conversions ─────────────────────────────────────────
    video_inputs = ("mp4", "mkv", "mov", "webm")

    if src_ext in video_inputs and target == "mp4":
        out = os.path.join(temp, f"{uid}_out.mp4")
        video_to_mp4(input_path, out)
        return out, "video/mp4", "converted.mp4"

    if src_ext in video_inputs and target == "mp4-720p":
        out = os.path.join(temp, f"{uid}_out.mp4")
        video_to_mp4_720p(input_path, out)
        return out, "video/mp4", "converted_720p.mp4"

    if src_ext in video_inputs and target == "mp4-1080p":
        out = os.path.join(temp, f"{uid}_out.mp4")
        video_to_mp4_1080p(input_path, out)
        return out, "video/mp4", "converted_1080p.mp4"

    if src_ext in video_inputs and target == "webm":
        out = os.path.join(temp, f"{uid}_out.webm")
        video_to_webm(input_path, out)
        return out, "video/webm", "converted.webm"

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

    # ── PDF → PDF/A ───────────────────────────────────────────────
    if src_ext == "pdf" and target == "pdf-a":
        out = os.path.join(temp, f"{uid}_out.pdf")
        pdf_to_pdfa(input_path, out)
        return out, "application/pdf", "converted_pdfa.pdf"

    # ── OCR: image/PDF → searchable PDF ───────────────────────────
    raster_ocr = ("jpg", "jpeg", "png", "webp", "bmp", "tiff", "tif", "heic", "heif", "avif")

    if src_ext in raster_ocr and target == "ocr-pdf":
        out = os.path.join(temp, f"{uid}_out.pdf")
        image_to_ocr_pdf(input_path, out)
        return out, "application/pdf", "converted_ocr.pdf"

    if src_ext == "pdf" and target == "ocr-pdf":
        out = os.path.join(temp, f"{uid}_out.pdf")
        pdf_to_ocr_pdf(input_path, out)
        return out, "application/pdf", "converted_ocr.pdf"

    # ── OCR: image/PDF → txt ──────────────────────────────────────
    if src_ext in raster_ocr and target == "txt":
        out = os.path.join(temp, f"{uid}_out.txt")
        image_to_txt(input_path, out)
        return out, "text/plain", "converted.txt"

    if src_ext == "pdf" and target == "txt":
        out = os.path.join(temp, f"{uid}_out.txt")
        pdf_to_txt(input_path, out)
        return out, "text/plain", "converted.txt"

    raise ValueError(f"No handler for {src_ext} → {target}")
