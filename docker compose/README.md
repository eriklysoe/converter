# Converter

A self-hosted file format converter with a drag-and-drop web UI. Supports conversion between images, PDFs, vector graphics, and documents.

## Quick Start

1. Create a `.env` file next to `docker-compose.yml` with your credentials:

```env
ADMIN_USER=admin
ADMIN_PASS=changeme
BASE_URL=http://localhost:7391
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
| `BASE_URL` | No | `http://localhost:7391` | Public-facing URL (for reverse proxy setups) |
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

When behind a reverse proxy, set `BASE_URL` in your `.env` file to the public-facing URL (e.g., `https://converter.yourdomain.com`) and forward traffic to port `7391`. The app includes ProxyFix middleware to trust `X-Forwarded-*` headers.
