import logging
from PIL import Image
from pillow_heif import register_heif_opener

# Register HEIC/HEIF support with Pillow
register_heif_opener()

logger = logging.getLogger(__name__)

FORMAT_MAP = {
    "jpg": "JPEG",
    "jpeg": "JPEG",
    "png": "PNG",
    "webp": "WEBP",
    "bmp": "BMP",
    "tiff": "TIFF",
    "tif": "TIFF",
    "ico": "ICO",
    "avif": "AVIF",
}

# Formats that require RGB (no alpha channel)
RGB_ONLY_FORMATS = {"JPEG", "BMP", "TIFF"}


def convert_image(input_path: str, output_path: str, target_ext: str) -> None:
    """Convert an image file to another format using Pillow."""
    pil_format = FORMAT_MAP.get(target_ext.lower(), target_ext.upper())
    logger.info("Converting image to %s", pil_format)

    with Image.open(input_path) as img:
        # Convert RGBA to RGB for formats that don't support alpha
        if pil_format in RGB_ONLY_FORMATS and img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        save_kwargs = {"format": pil_format}
        if pil_format in ("JPEG", "WEBP", "AVIF"):
            save_kwargs["quality"] = 95
        if pil_format == "ICO":
            # ICO requires specific sizes; use largest that fits
            size = min(img.size[0], img.size[1], 256)
            img = img.resize((size, size), Image.LANCZOS)

        img.save(output_path, **save_kwargs)


def convert_raw_to_image(input_path: str, output_path: str, target_ext: str) -> None:
    """Convert RAW camera files (CR2, NEF, ARW) to JPG/PNG via dcraw + Pillow."""
    import subprocess
    import os

    # dcraw outputs a PPM file alongside the input
    cmd = ["dcraw", "-c", "-w", "-T", input_path]
    tiff_path = output_path + ".tmp.tiff"
    with open(tiff_path, "wb") as f:
        result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, text=False)
    if result.returncode != 0:
        if os.path.exists(tiff_path):
            os.remove(tiff_path)
        raise RuntimeError(f"dcraw failed: {result.stderr.decode()}")

    try:
        with Image.open(tiff_path) as img:
            if target_ext in ("jpg", "jpeg"):
                img.convert("RGB").save(output_path, "JPEG", quality=95)
            else:
                img.save(output_path, "PNG")
    finally:
        if os.path.exists(tiff_path):
            os.remove(tiff_path)

    logger.info("Converted RAW to %s", target_ext)


def convert_gif_webp(input_path: str, output_path: str, target_ext: str) -> None:
    """Convert between GIF and WebP, preserving animation."""
    with Image.open(input_path) as img:
        if getattr(img, "n_frames", 1) > 1:
            # Animated
            frames = []
            durations = []
            for i in range(img.n_frames):
                img.seek(i)
                frame = img.copy()
                if target_ext in ("jpg", "jpeg"):
                    frame = frame.convert("RGB")
                frames.append(frame)
                durations.append(img.info.get("duration", 100))

            if target_ext == "webp":
                frames[0].save(output_path, "WEBP", save_all=True,
                               append_images=frames[1:], duration=durations, loop=0, quality=90)
            elif target_ext == "gif":
                frames[0].save(output_path, "GIF", save_all=True,
                               append_images=frames[1:], duration=durations, loop=0)
        else:
            # Static
            save_fmt = "WEBP" if target_ext == "webp" else "GIF"
            kwargs = {"quality": 90} if target_ext == "webp" else {}
            img.save(output_path, save_fmt, **kwargs)

    logger.info("Converted to %s (animated: %s)", target_ext,
                getattr(Image.open(input_path), "n_frames", 1) > 1)
