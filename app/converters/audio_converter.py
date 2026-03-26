import subprocess
import logging

logger = logging.getLogger(__name__)


def _ffmpeg_audio(input_path: str, output_path: str, codec_args: list) -> None:
    """Generic ffmpeg audio conversion."""
    cmd = ["ffmpeg", "-y", "-i", input_path] + codec_args + [output_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr}")


def audio_to_mp3_320(input_path: str, output_path: str) -> None:
    """Convert audio to MP3 at constant 320 kbps."""
    _ffmpeg_audio(input_path, output_path, ["-codec:a", "libmp3lame", "-b:a", "320k"])


def audio_to_mp3_vbr(input_path: str, output_path: str) -> None:
    """Convert audio to MP3 using VBR V0 (~245 kbps)."""
    _ffmpeg_audio(input_path, output_path, ["-codec:a", "libmp3lame", "-q:a", "0"])


def audio_to_wav(input_path: str, output_path: str) -> None:
    """Convert audio to WAV (24-bit PCM)."""
    _ffmpeg_audio(input_path, output_path, ["-codec:a", "pcm_s24le"])


def audio_to_flac(input_path: str, output_path: str) -> None:
    """Convert audio to FLAC (compression level 8)."""
    _ffmpeg_audio(input_path, output_path, ["-codec:a", "flac", "-compression_level", "8"])


def audio_to_ogg(input_path: str, output_path: str) -> None:
    """Convert audio to OGG Vorbis (quality 6, ~192 kbps)."""
    _ffmpeg_audio(input_path, output_path, ["-codec:a", "libvorbis", "-q:a", "6"])


def audio_to_aiff(input_path: str, output_path: str) -> None:
    """Convert audio to AIFF (16-bit PCM)."""
    _ffmpeg_audio(input_path, output_path, ["-codec:a", "pcm_s16be"])
