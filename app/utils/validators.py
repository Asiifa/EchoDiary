"""Data and audio file validators."""
import os
import re
from pathlib import Path
from typing import Tuple, Dict, Any
import soundfile as sf
from app.config import Config


class AudioValidationError(Exception):
    """Raised when an audio file cannot be processed or is invalid."""
    pass


def sanitize_filename(name: str) -> str:
    """Sanitize a string to be safely used as a filename."""
    # Replace non-alphanumeric (except underscores and hyphens)
    clean = re.sub(r"[^\w\-.]", "_", name)
    return clean[:100]


def validate_audio_file(file_path: str) -> Dict[str, Any]:
    """
    Validate that the given audio file exists, has a supported format,
    and can be opened and parsed for duration, samplerate, and channels.
    """
    path = Path(file_path)
    if not path.exists():
        raise AudioValidationError(f"Audio file does not exist: {file_path}")

    if not path.is_file():
        raise AudioValidationError(f"Path is not a regular file: {file_path}")

    file_size = path.stat().st_size
    if file_size == 0:
        raise AudioValidationError("Audio file is empty (0 bytes).")

    ext = path.suffix.lower()
    if ext not in Config.SUPPORTED_AUDIO_EXTENSIONS:
        supported_str = ", ".join(Config.SUPPORTED_AUDIO_EXTENSIONS)
        raise AudioValidationError(
            f"Unsupported audio format '{ext}'. Supported formats are: {supported_str}"
        )

    try:
        with sf.SoundFile(str(path)) as f:
            duration = len(f) / float(f.samplerate)
            if duration <= 0:
                raise AudioValidationError("Audio duration is zero seconds.")
            return {
                "valid": True,
                "file_path": str(path.resolve()),
                "duration_seconds": round(duration, 2),
                "samplerate": f.samplerate,
                "channels": f.channels,
                "format": f.format,
                "subtype": f.subtype,
                "size_bytes": file_size,
            }
    except Exception as e:
        if isinstance(e, AudioValidationError):
            raise
        raise AudioValidationError(f"Failed to read audio file '{path.name}': {str(e)}")

