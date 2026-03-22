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
