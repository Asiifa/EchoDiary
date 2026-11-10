"""Tests for local transcription service and audio validation."""
import pytest
from pathlib import Path
from app.utils.validators import validate_audio_file, AudioValidationError
from app.services.transcription_service import TranscriptionService, TranscriptionError


def test_validate_valid_audio(sample_wav_file):
    """Verify validation passes on generated WAV file."""
    res = validate_audio_file(str(sample_wav_file))
    assert res["valid"] is True
    assert res["duration_seconds"] > 1.8
    assert res["samplerate"] == 16000


def test_validate_nonexistent_audio(temp_dir):
    """Validation must raise AudioValidationError when file does not exist."""
    fake_path = temp_dir / "nonexistent.wav"
    with pytest.raises(AudioValidationError, match="does not exist"):
        validate_audio_file(str(fake_path))


def test_validate_empty_audio(temp_dir):
    """Validation must reject 0-byte audio files."""
    empty_path = temp_dir / "empty.wav"
    empty_path.write_bytes(b"")
    with pytest.raises(AudioValidationError, match="is empty"):
        validate_audio_file(str(empty_path))


def test_validate_unsupported_audio_format(temp_dir):
    """Validation must reject unsupported file extensions."""
    txt_path = temp_dir / "audio.txt"
    txt_path.write_text("not an audio file")
    with pytest.raises(AudioValidationError, match="Unsupported audio format"):
        validate_audio_file(str(txt_path))


def test_transcription_service_initialization():
    """Verify transcription service accepts configured model names."""
    service = TranscriptionService(model_size="base")
    assert service.model_size == "base"
    assert service.device == "cpu"
    assert service.compute_type == "int8"

