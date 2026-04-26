import os
import json
import subprocess
import logging

logger = logging.getLogger(__name__)


def _ffmpeg_audio(input_path: str, output_path: str, codec_args: list) -> None:
    """Generic ffmpeg audio conversion."""
    cmd = ["ffmpeg", "-y", "-i", input_path] + codec_args + [output_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr}")


def audio_to_mp3_cbr(input_path: str, output_path: str, bitrate_kbps: int) -> None:
    """Convert audio to MP3 at a constant bitrate (kbps)."""
    _ffmpeg_audio(input_path, output_path, ["-codec:a", "libmp3lame", "-b:a", f"{bitrate_kbps}k"])


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


def audio_to_m4a(input_path: str, output_path: str) -> None:
    """Convert audio to M4A/AAC (256 kbps)."""
    _ffmpeg_audio(input_path, output_path, ["-codec:a", "aac", "-b:a", "256k"])


def audio_to_m4b_copy(input_path: str, output_path: str) -> None:
    """Wrap audio (and cover art if present) in an m4b container without re-encoding."""
    _ffmpeg_audio(input_path, output_path,
                  ["-map", "0:a", "-map", "0:v?", "-c", "copy", "-f", "ipod"])


def audio_to_m4b_aac(input_path: str, output_path: str, bitrate_kbps: int) -> None:
    """Re-encode audio to AAC inside an m4b container at the given bitrate (kbps)."""
    _ffmpeg_audio(input_path, output_path,
                  ["-map", "0:a", "-map", "0:v?",
                   "-c:a", "aac", "-b:a", f"{bitrate_kbps}k",
                   "-c:v", "copy", "-f", "ipod"])


def get_duration(input_path: str) -> float:
    """Return audio duration in seconds via ffprobe."""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", input_path],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe duration failed: {result.stderr}")
    try:
        return float(result.stdout.strip())
    except ValueError:
        raise RuntimeError(f"Could not parse duration: {result.stdout!r}")


def get_input_bitrate_kbps(input_path: str) -> int:
    """Return the audio stream bitrate in kbps (falls back to format-level)."""
    for args in (["-select_streams", "a:0", "-show_entries", "stream=bit_rate"],
                 ["-show_entries", "format=bit_rate"]):
        cmd = ["ffprobe", "-v", "error"] + args + ["-of", "csv=p=0", input_path]
        result = subprocess.run(cmd, capture_output=True, text=True)
        try:
            v = int(result.stdout.strip())
            if v > 0:
                return v // 1000
        except ValueError:
            continue
    return 128


def _ffmpeg_segment(input_path: str, start: float, end: float,
                    output_path: str, ffmpeg_args: list) -> None:
    cmd = ["ffmpeg", "-y", "-i", input_path,
           "-ss", str(start), "-to", str(end)] + list(ffmpeg_args) + [output_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg segment failed: {result.stderr}")


def get_chapters(input_path: str) -> list:
    """Return list of (start_s, end_s, title) tuples for chapters in the input."""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-i", input_path,
         "-show_chapters", "-print_format", "json"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr}")
    data = json.loads(result.stdout or "{}")
    return [
        (float(ch.get("start_time", 0)),
         float(ch.get("end_time", 0)),
         ch.get("tags", {}).get("title", ""))
        for ch in data.get("chapters", [])
    ]


def split_by_chapters(input_path: str, output_dir: str, base_name: str,
                      chapters_per_part: int, ffmpeg_args: list,
                      output_ext: str) -> list:
    """Split input by chapter boundaries into parts of N chapters each.

    ffmpeg_args is the list of codec/mapping/format flags between -i and the output
    (e.g. ["-map", "0:a", "-c", "copy", "-f", "ipod"]). Returns list of output paths.
    """
    if chapters_per_part < 1:
        raise ValueError("chapters_per_part must be >= 1")
    chapters = get_chapters(input_path)
    if not chapters:
        raise RuntimeError("No chapters found in input — cannot split by chapters")

    out_paths = []
    total = len(chapters)
    for i in range(0, total, chapters_per_part):
        start = chapters[i][0]
        end_idx = min(i + chapters_per_part - 1, total - 1)
        end = chapters[end_idx][1]
        part_num = (i // chapters_per_part) + 1
        out_path = os.path.join(output_dir, f"{base_name}_part_{part_num:02d}.{output_ext}")
        _ffmpeg_segment(input_path, start, end, out_path, ffmpeg_args)
        out_paths.append(out_path)
        logger.info("Split part %d: chapters %d-%d → %s",
                    part_num, i + 1, end_idx + 1, out_path)
    return out_paths


def split_by_size(input_path: str, output_dir: str, base_name: str,
                  target_size_mb: int, ffmpeg_args: list, output_ext: str,
                  est_bitrate_kbps: int) -> list:
    """Split input into time windows that each encode to ~target_size_mb.

    Window length is computed from the estimated output bitrate; actual file
    sizes will be approximate (close but not exact).
    """
    if target_size_mb <= 0:
        raise ValueError("target_size_mb must be > 0")
    if est_bitrate_kbps <= 0:
        raise ValueError("est_bitrate_kbps must be > 0")
    duration = get_duration(input_path)
    if duration <= 0:
        raise RuntimeError("Could not determine input duration")

    seconds_per_part = (target_size_mb * 1024 * 1024 * 8) / (est_bitrate_kbps * 1000)
    out_paths = []
    part = 1
    start = 0.0
    while start < duration - 0.1:
        end = min(start + seconds_per_part, duration)
        out_path = os.path.join(output_dir, f"{base_name}_part_{part:02d}.{output_ext}")
        _ffmpeg_segment(input_path, start, end, out_path, ffmpeg_args)
        out_paths.append(out_path)
        logger.info("Split-by-size part %d: %.1f-%.1fs → %s", part, start, end, out_path)
        start = end
        part += 1
    return out_paths
