import os
import subprocess
import logging

logger = logging.getLogger(__name__)


def video_to_mp4(input_path: str, output_path: str) -> None:
    """Re-encode video to MP4 (H.264 + AAC)."""
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-codec:v", "libx264", "-preset", "medium", "-crf", "23",
        "-codec:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg video→MP4 failed: {result.stderr}")
    logger.info("Converted video to MP4")


def video_to_mp3(input_path: str, output_path: str) -> None:
    """Extract audio from video as MP3 320 kbps."""
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vn", "-codec:a", "libmp3lame", "-b:a", "320k",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg video→MP3 failed: {result.stderr}")
    logger.info("Extracted audio to MP3")


def video_to_gif(input_path: str, output_path: str) -> None:
    """Convert video to GIF using two-pass palette for quality."""
    palette = output_path + ".palette.png"
    try:
        cmd1 = [
            "ffmpeg", "-y", "-i", input_path,
            "-vf", "fps=15,scale=480:-1:flags=lanczos,palettegen",
            palette,
        ]
        result = subprocess.run(cmd1, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg palette generation failed: {result.stderr}")

        cmd2 = [
            "ffmpeg", "-y", "-i", input_path, "-i", palette,
            "-lavfi", "fps=15,scale=480:-1:flags=lanczos[x];[x][1:v]paletteuse",
            output_path,
        ]
        result = subprocess.run(cmd2, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg GIF conversion failed: {result.stderr}")
        logger.info("Converted video to GIF")
    finally:
        if os.path.exists(palette):
            os.remove(palette)
