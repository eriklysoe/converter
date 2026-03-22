# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Self-hosted file format converter with a drag-and-drop web UI. Flask backend dispatches file conversions to modular converter classes that wrap external tools (Inkscape, Ghostscript, LibreOffice) and Python libraries (Pillow, pillow-heif, ReportLab, python-docx, python-pptx, pypdf).

## Build & Run

```bash
# Docker (primary method)
docker compose up --build

# Local development (requires Inkscape, Ghostscript, LibreOffice, pdftk-java installed)
pip install -r requirements.txt
ADMIN_USER=admin ADMIN_PASS=changeme python app/app.py  # Serves on 0.0.0.0:7391
```

The app requires `ADMIN_USER` and `ADMIN_PASS` env vars — it refuses to start without them. HTTP Basic Auth protects all routes.

No test suite or linter is configured.

## Architecture

**Request flow**: Upload → `routes.py:dispatch()` → converter module → download response (ZIP if multi-page output)

### Key files

- `app/app.py` — Flask app factory, configures `MAX_CONTENT_LENGTH` (from `MAX_FILE_SIZE` in MB) and `TEMP_DIR` from env vars. Enforces auth env vars on startup.
- `app/routes.py` — Three endpoints (`/`, `/api/formats`, `/api/convert`), `CONVERSION_MAP` dict defining all conversion paths, `dispatch()` function routing to converters, `require_auth` decorator (HTTP Basic Auth).
- `app/converters/image_converter.py` — Pillow-based raster↔raster (JPG, PNG, WebP, BMP, TIFF, ICO, AVIF, HEIC/HEIF). Registers `pillow-heif` opener at import.
- `app/converters/pdf_converter.py` — PDF→image/SVG (Inkscape `--pdf-poppler`, JPG via PNG+Pillow), image→PDF (ReportLab), PDF merge (pypdf)
- `app/converters/document_converter.py` — DOCX/DOC/ODT/PPTX/XLSX/RTF→PDF (LibreOffice headless), PDF→DOCX (image-based: Inkscape PNG render into python-docx, scaled to A4), PDF→ODT (via DOCX then LibreOffice), PDF→PPTX (PDF→SVG→EMF→python-pptx, one vector object per slide)
- `app/converters/eps_converter.py` — EPS↔image/SVG/PDF via Ghostscript (EPS↔PDF) + Inkscape (rasterization). Inkscape 1.2 cannot read EPS directly.

### Conversion dispatch pattern

`CONVERSION_MAP` in `routes.py` maps source format strings to lists of valid target formats. `dispatch()` matches `(src_ext, target)` and calls the appropriate converter. Adding a new conversion means: implement the function in the appropriate converter module, add the target to the source's list in `CONVERSION_MAP`, and add a dispatch case.

### External tool invocations

Converters shell out to Inkscape, Ghostscript, and LibreOffice via `subprocess.run()`. These must be available on PATH (handled by Dockerfile).

Key constraints:
- **Inkscape** does not support direct JPG export or EPS import — use PNG then convert via Pillow; use Ghostscript for EPS.
- **Ghostscript** handles all EPS read/write (`gs -sDEVICE=pdfwrite` for EPS→PDF, `gs -sDEVICE=eps2write` for PDF→EPS).
- **LibreOffice** needs `--infilter` for PDF imports and unique `-env:UserInstallation` temp dirs to avoid lock collisions.
- **SVG→raster** must route through Inkscape, not Pillow (Pillow cannot open SVG files).
- **PDF→DOCX** renders pages as images scaled to A4 (landscape/portrait auto-detected). Word has a 22-inch max page width.
- **PDF→PPTX** uses SVG→EMF pipeline for single resizable vector objects per slide.

### Temp file handling

Input files are saved to a temp directory, processed, then cleaned up. Multi-page outputs (e.g., PDF→PNG) are zipped. Output files rely on OS temp cleanup.

## Environment Variables

- `ADMIN_USER` — Username for HTTP Basic Auth (required)
- `ADMIN_PASS` — Password for HTTP Basic Auth (required)
- `MAX_FILE_SIZE` — Max upload size in MB (default: `50`)
- `PUID` / `PGID` — Container user/group ID (linuxserver.io pattern, handled by `entrypoint.sh`)
- `TZ` — Timezone for container

## Frontend

Single-page app in `app/templates/index.html` + `app/static/js/app.js` + `app/static/css/style.css`. Communicates with backend via `/api/formats` (get valid conversions) and `/api/convert` (upload and convert). Format buttons are dynamically populated from the backend.
