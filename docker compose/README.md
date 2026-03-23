# Converter

A self-hosted file format converter with a drag-and-drop web UI. Supports conversion between images, PDFs, vector graphics, and documents.

## Quick Start

1. Edit `docker-compose.yml` and set your credentials:

```yaml
- ADMIN_USER=changeme
- ADMIN_PASS=changeme
```

2. Start the container:

```bash
docker compose up -d
```

Open `http://localhost:7391` in your browser and log in with your credentials.

## Docker Hub

```
docker pull eriklysoe/converter:latest
```

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `ADMIN_USER` | **Yes** | — | Username for web UI login |
| `ADMIN_PASS` | **Yes** | — | Password for web UI login |
| `MAX_FILE_SIZE` | No | `50` | Max upload size in MB |
| `PUID` | No | `1000` | Run as this user ID |
| `PGID` | No | `1000` | Run as this group ID |
| `TZ` | No | `Etc/UTC` | Timezone for the container |

## Supported Conversions

- **Images**: JPG, PNG, WebP, BMP, TIFF, ICO, AVIF, HEIC/HEIF
- **Vector**: SVG, EPS
- **PDF**: to/from images, documents, and vector formats
- **Documents**: DOCX, ODT, PPTX, XLSX, RTF → PDF

## Reverse Proxy

When behind a reverse proxy, update the port mapping or set up your proxy to forward to port `7391`.
