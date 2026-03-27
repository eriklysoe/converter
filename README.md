# converter

[![GitHub](https://img.shields.io/badge/github-converter-00d4aa?style=flat-square&logo=github)](https://github.com/eriklysoe/converter)
[![Docker](https://img.shields.io/badge/docker-ready-00d4aa?style=flat-square&logo=docker)](https://github.com/eriklysoe/converter)

A self-hosted file format converter. Drag, drop, convert, download.

## Supported conversions

### Images

| Input        | Output                        | Engine          |
|--------------|-------------------------------|-----------------|
| JPG/PNG/WebP/BMP/TIFF/AVIF | any of the above ↔ | Pillow          |
| HEIC/HEIF    | JPG, PNG, WebP, BMP, TIFF, AVIF, PDF, EPS | Pillow + pillow-heif |
| ICO          | JPG, PNG, WebP, BMP, TIFF, AVIF | Pillow          |
| Image        | ICO                           | Pillow          |
| GIF          | WebP, PNG, JPG                | Pillow          |
| WebP         | GIF                           | Pillow          |
| CR2/NEF/ARW (RAW) | JPG, PNG                 | rawpy + Pillow  |
| SVG          | PNG, JPG, EPS                 | Inkscape + Ghostscript |
| EPS          | PNG, JPG, SVG, PDF            | Ghostscript + Inkscape |
| Image/SVG/PDF | EPS                          | Ghostscript     |

### Documents

| Input        | Output                        | Engine          |
|--------------|-------------------------------|-----------------|
| Image        | PDF                           | ReportLab       |
| PDF          | PNG, JPG (per page)           | Inkscape + Pillow |
| PDF          | SVG (per page, high quality)  | Inkscape        |
| PDF          | DOCX (image-based, A4 scaled) | Inkscape + python-docx |
| PDF          | ODT                           | via DOCX + LibreOffice |
| PDF          | PPTX (vector, one object/slide) | Inkscape SVG→EMF + python-pptx |
| DOCX/DOC/ODT/PPTX/XLSX/RTF | PDF             | LibreOffice     |
| Markdown     | PDF                           | LibreOffice     |
| CSV          | XLSX                          | openpyxl        |
| XLSX         | CSV                           | openpyxl        |

### Audio

| Input        | Output                        | Engine          |
|--------------|-------------------------------|-----------------|
| FLAC/WAV/MP3/OGG/M4A/AAC/AIFF | MP3 (320 kbps CBR) | FFmpeg |
| FLAC/WAV/OGG/M4A/AAC/AIFF | MP3 (V0 VBR)        | FFmpeg          |
| FLAC/MP3/OGG/M4A/AAC/AIFF | WAV                  | FFmpeg          |
| WAV/MP3/OGG/M4A/AAC/AIFF  | FLAC                 | FFmpeg          |
| FLAC/WAV/MP3/M4A/AAC/AIFF | OGG                  | FFmpeg          |
| FLAC/WAV/MP3/OGG/M4A/AAC  | AIFF                 | FFmpeg          |

### Video

| Input        | Output                        | Engine          |
|--------------|-------------------------------|-----------------|
| MKV/MOV      | MP4                           | FFmpeg          |
| MP4/MKV/MOV  | MP3 (audio extract)           | FFmpeg          |
| MP4/MKV/MOV  | GIF                           | FFmpeg          |

Multi-file uploads supported with batch conversion (ZIP output) or merge into a single DOCX/PPTX/PDF. Multi-page outputs are bundled as a ZIP download.

## Usage

1. Create a `.env` file with your credentials:

```env
ADMIN_USER=admin
ADMIN_PASS=changeme
BASE_URL=http://localhost:7391
```

2. Create a `docker-compose.yml`:

```yaml
services:
  converter:
    image: ghcr.io/eriklysoe/converter:latest
    container_name: converter
    env_file: .env
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=Etc/UTC
      - MAX_FILE_SIZE=50
    volumes:
      - ./config:/config
    ports:
      - "7391:7391"
    restart: unless-stopped
```

3. Start the container:

```bash
docker compose up -d
```

Then open `http://your-server:7391`. The browser will prompt for username and password.

## Parameters

| Parameter | Function |
|-----------|----------|
| `PUID` | User ID for file permissions |
| `PGID` | Group ID for file permissions |
| `TZ` | Timezone (e.g. `Etc/UTC`) |
| `MAX_FILE_SIZE` | Max upload size in MB (default `50`) |
| `ADMIN_USER` | Username for HTTP Basic Auth (required, in `.env`) |
| `ADMIN_PASS` | Password for HTTP Basic Auth (required, in `.env`) |
| `BASE_URL` | Public-facing URL for reverse proxy setups (default `http://localhost:7391`) |

## Build locally

```bash
git clone https://github.com/eriklysoe/converter
cd converter
docker compose up --build
```

## Notes

- Inkscape is used for all PDF→SVG and PDF→image conversions for maximum quality (`--pdf-poppler` flag preserves text as selectable elements).
- Ghostscript handles all EPS import/export (Inkscape 1.2+ cannot read EPS directly).
- LibreOffice handles office document conversions headless.
- FFmpeg handles all audio and video conversions. MP3 encoding offers both 320 kbps CBR and LAME V0 VBR options.
- RAW camera files (CR2, NEF, ARW) are converted via rawpy + Pillow.
- PDF→DOCX renders each page as a 300 DPI image scaled to fit A4 (landscape/portrait auto-detected). This avoids clipping issues with non-standard page sizes.
- PDF→PPTX converts via SVG→EMF so each page is a single resizable vector object per slide.
- PDF→ODT converts via the DOCX pipeline then LibreOffice DOCX→ODT.
- HEIC/HEIF support requires pillow-heif (included in requirements).
- `ADMIN_USER` and `ADMIN_PASS` must both be set or the app will refuse to start.
- Temporary files are cleaned up after each conversion.
- The Docker image is large due to Inkscape + Ghostscript + LibreOffice + FFmpeg. This is expected.
