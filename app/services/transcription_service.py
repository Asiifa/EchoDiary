"""Local speech recognition service using faster-whisper."""
import os
import threading
from pathlib import Path
from typing import Optional, Dict, Any, Callable
from app.config import Config
from app.utils.validators import validate_audio_file, AudioValidationError


class TranscriptionError(Exception):
    """Exception raised for transcription failures."""
    pass


class TranscriptionService:
    """
    Offline local transcription using faster-whisper.
    Runs strictly on local CPU with int8 quantization.
    """

    _cached_models: Dict[str, Any] = {}
    _model_lock = threading.Lock()

    def __init__(
        self,
        model_size: str = Config.DEFAULT_WHISPER_MODEL,
        device: str = Config.DEFAULT_WHISPER_DEVICE,
        compute_type: str = Config.DEFAULT_WHISPER_COMPUTE_TYPE,
    ):
        self.model_size = model_size if model_size in Config.WHISPER_MODELS else Config.DEFAULT_WHISPER_MODEL
        self.device = device
        self.compute_type = compute_type

    def get_model(self):
        """Lazy-load and cache the faster-whisper model instance."""
        from faster_whisper import WhisperModel

        cache_key = f"{self.model_size}_{self.device}_{self.compute_type}"
        with self._model_lock:
            if cache_key not in self._cached_models:
                try:
                    # Model files are loaded from local HuggingFace cache or downloaded to local cache
                    model = WhisperModel(
                        self.model_size,
                        device=self.device,
                        compute_type=self.compute_type,
                        cpu_threads=4,
                    )
                    self._cached_models[cache_key] = model
                except Exception as e:
                    raise TranscriptionError(f"Failed to load Whisper model '{self.model_size}': {str(e)}")
            return self._cached_models[cache_key]

    def transcribe(
        self,
        audio_file_path: str,
        language: Optional[str] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> Dict[str, Any]:
        """
        Transcribe the given audio file using local faster-whisper.
        Emits progress updates if progress_callback is provided.
        """
        # Validate audio first
        validation = validate_audio_file(audio_file_path)
        total_duration = validation["duration_seconds"]

        if progress_callback:
            progress_callback(0.1, "Initializing local Whisper model...")

        model = self.get_model()

        if progress_callback:
            progress_callback(0.25, "Processing audio segments...")

        try:
            # Language handling: None or 'auto' means automatic language detection
            lang_param = None if (not language or language.lower() in ("auto", "none")) else language.lower()

            segments_gen, info = model.transcribe(
                str(audio_file_path),
                beam_size=5,
                language=lang_param,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500),
            )

            detected_lang = info.language
            detected_prob = round(info.language_probability, 3)

            transcript_pieces = []
            segment_list = []

            for seg in segments_gen:
                text = seg.text.strip()
                if text:
                    transcript_pieces.append(text)
                    segment_list.append({
                        "id": seg.id,
                        "start": round(seg.start, 2),
                        "end": round(seg.end, 2),
                        "text": text,
                    })

                if progress_callback and total_duration > 0:
                    pct = min(0.95, 0.25 + 0.70 * (seg.end / total_duration))
                    progress_callback(pct, f"Transcribing... ({round(seg.end, 1)}s / {round(total_duration, 1)}s)")

            full_transcript = " ".join(transcript_pieces).strip()

            if not full_transcript:
                # Handled cleanly without crashing
                full_transcript = "[No audible speech detected in recording]"

            if progress_callback:
                progress_callback(1.0, "Transcription completed.")

            return {
                "text": full_transcript,
                "language": detected_lang,
                "language_probability": detected_prob,
                "duration_seconds": total_duration,
                "segments": segment_list,
            }

        except Exception as e:
            if isinstance(e, (TranscriptionError, AudioValidationError)):
                raise
            raise TranscriptionError(f"Transcription error: {str(e)}")

