# converter

[![GitHub](https://img.shields.io/badge/github-converter-00d4aa?style=flat-square&logo=github)](https://github.com/yourusername/converter)
[![Docker](https://img.shields.io/badge/docker-ready-00d4aa?style=flat-square&logo=docker)](https://github.com/yourusername/converter)

A self-hosted file format converter. Drag, drop, convert, download.

## Supported conversions

| Input        | Output                        | Engine          |
|--------------|-------------------------------|-----------------|
| JPG/PNG/WebP/BMP/TIFF/AVIF | any of the above ↔ | Pillow          |
| HEIC/HEIF    | JPG, PNG, WebP, BMP, TIFF, AVIF, PDF, EPS | Pillow + pillow-heif |
| ICO          | JPG, PNG, WebP, BMP, TIFF, AVIF | Pillow          |
| Image        | ICO                           | Pillow          |
| SVG          | PNG, JPG, EPS                 | Inkscape + Ghostscript |
| EPS          | PNG, JPG, SVG, PDF            | Ghostscript + Inkscape |
| Image/SVG/PDF | EPS                          | Ghostscript     |
| Image        | PDF                           | ReportLab       |
| PDF          | PNG, JPG (per page)           | Inkscape + Pillow |
| PDF          | SVG (per page, high quality)  | Inkscape        |
| PDF          | DOCX (image-based, A4 scaled) | Inkscape + python-docx |
| PDF          | ODT                           | via DOCX + LibreOffice |
| PDF          | PPTX (vector, one object/slide) | Inkscape SVG→EMF + python-pptx |
| DOCX/DOC/ODT/PPTX/XLSX/RTF | PDF             | LibreOffice     |

Multi-file uploads supported with batch conversion (ZIP output) or merge into a single DOCX/PPTX/PDF. Multi-page outputs are bundled as a ZIP download.

## Usage

```yaml
services:
  converter:
    image: ghcr.io/yourusername/converter:latest
    container_name: converter
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=Europe/Oslo
      - MAX_FILE_SIZE=50       # in MB
      - ADMIN_USER=admin       # required
      - ADMIN_PASS=changeme    # required
    volumes:
      - ./config:/config
    ports:
      - "7391:7391"
    restart: unless-stopped
```

Then open `http://your-server:7391`. The browser will prompt for username and password.

## Parameters

| Parameter | Function |
|-----------|----------|
| `PUID` | User ID for file permissions |
| `PGID` | Group ID for file permissions |
| `TZ` | Timezone (e.g. `Europe/Oslo`) |
| `MAX_FILE_SIZE` | Max upload size in MB (default `50`) |
| `ADMIN_USER` | Username for HTTP Basic Auth (required) |
| `ADMIN_PASS` | Password for HTTP Basic Auth (required) |

## Build locally

```bash
git clone https://github.com/yourusername/converter
cd converter
docker compose up --build
```

## Notes

- Inkscape is used for all PDF→SVG and PDF→image conversions for maximum quality (`--pdf-poppler` flag preserves text as selectable elements).
- Ghostscript handles all EPS import/export (Inkscape 1.2+ cannot read EPS directly).
- LibreOffice handles office document conversions headless.
- PDF→DOCX renders each page as a 300 DPI image scaled to fit A4 (landscape/portrait auto-detected). This avoids clipping issues with non-standard page sizes.
- PDF→PPTX converts via SVG→EMF so each page is a single resizable vector object per slide.
- PDF→ODT converts via the DOCX pipeline then LibreOffice DOCX→ODT.
- HEIC/HEIF support requires pillow-heif (included in requirements).
- `ADMIN_USER` and `ADMIN_PASS` must both be set or the app will refuse to start.
- Temporary files are cleaned up after each conversion.
- The Docker image is large (~1.5 GB) due to Inkscape + Ghostscript + LibreOffice. This is expected.
