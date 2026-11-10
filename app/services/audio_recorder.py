"""Audio recording service using sounddevice and soundfile."""
import time
import threading
import queue
from pathlib import Path
from typing import List, Dict, Optional, Callable, Any
import numpy as np
import sounddevice as sd
import soundfile as sf
from app.config import Config


class AudioRecorderError(Exception):
    """Exception raised for recording errors."""
    pass


class AudioRecorder:
    """
    Manages microphone device selection, live threaded audio recording,
    RMS level calculation for real-time visualization, pause/resume,
    and saving to standard WAV files.
    """

    STATE_IDLE = "IDLE"
    STATE_RECORDING = "RECORDING"
    STATE_PAUSED = "PAUSED"
    STATE_STOPPED = "STOPPED"

    def __init__(
        self,
        sample_rate: int = Config.AUDIO_SAMPLE_RATE,
        channels: int = Config.AUDIO_CHANNELS,
        level_callback: Optional[Callable[[float], None]] = None,
    ):
        self.sample_rate = sample_rate
        self.channels = channels
        self.level_callback = level_callback

        self.device_index: Optional[int] = None
        self.state = self.STATE_IDLE

        self._stream: Optional[sd.InputStream] = None
        self._recorded_chunks: List[np.ndarray] = []
        self._lock = threading.Lock()
        self._start_time: float = 0.0
        self._elapsed_seconds: float = 0.0
        self._last_resume_time: float = 0.0

    @staticmethod
    def get_input_devices() -> List[Dict[str, Any]]:
        """List all available microphone input devices."""
        devices = []
        try:
            device_list = sd.query_devices()
            default_input = sd.default.device[0]
            for idx, dev in enumerate(device_list):
                if dev.get("max_input_channels", 0) > 0:
                    devices.append({
                        "index": idx,
                        "name": dev.get("name", f"Device {idx}"),
                        "channels": dev.get("max_input_channels", 1),
                        "default_samplerate": dev.get("default_samplerate", 44100.0),
                        "is_default": (idx == default_input),
                    })
        except Exception as e:
            # Fallback if query fails
            devices.append({"index": None, "name": "Default Microphone", "channels": 1, "is_default": True})
        return devices

    def set_device(self, device_index: Optional[int]) -> None:
        """Set the active recording device by index."""
        if self.state in (self.STATE_RECORDING, self.STATE_PAUSED):
            raise AudioRecorderError("Cannot change device while recording is in progress.")
        self.device_index = device_index

    def _audio_callback(self, indata: np.ndarray, frames: int, time_info: Any, status: sd.CallbackFlags) -> None:
        """Sounddevice input stream callback invoked in audio thread."""
        if self.state != self.STATE_RECORDING:
            return

        # Copy incoming samples
        data_copy = indata.copy()
        with self._lock:
            self._recorded_chunks.append(data_copy)

        # Compute RMS level for UI meter
        if self.level_callback:
            # Root Mean Square of current chunk
            rms = np.sqrt(np.mean(data_copy**2)) if len(data_copy) > 0 else 0.0
            # Normalize: max audio level ~ 1.0, scale gracefully
            level = float(np.clip(rms * 4.0, 0.0, 1.0))
            try:
                self.level_callback(level)
            except Exception:
                pass

    def start_recording(self) -> None:
        """Start a fresh audio recording session."""
        if self.state in (self.STATE_RECORDING, self.STATE_PAUSED):
            raise AudioRecorderError("A recording session is already active.")

        with self._lock:
            self._recorded_chunks.clear()
            self._elapsed_seconds = 0.0

        try:
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                device=self.device_index,
                dtype="float32",
                callback=self._audio_callback,
            )
            self._stream.start()
        except Exception as e:
            self.state = self.STATE_IDLE
            raise AudioRecorderError(f"Failed to start audio recording: {str(e)}")

        self.state = self.STATE_RECORDING
        self._start_time = time.time()
        self._last_resume_time = self._start_time

    def pause_recording(self) -> None:
        """Pause active recording."""
        if self.state != self.STATE_RECORDING:
            return
        now = time.time()
        self._elapsed_seconds += (now - self._last_resume_time)
        self.state = self.STATE_PAUSED
        if self.level_callback:
            self.level_callback(0.0)

    def resume_recording(self) -> None:
        """Resume paused recording."""
        if self.state != self.STATE_PAUSED:
            return
        self._last_resume_time = time.time()
        self.state = self.STATE_RECORDING

    def stop_recording(self) -> float:
        """Stop recording and return total duration in seconds."""
        if self.state == self.STATE_RECORDING:
            now = time.time()
            self._elapsed_seconds += (now - self._last_resume_time)

        self.state = self.STATE_STOPPED

        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

        if self.level_callback:
            self.level_callback(0.0)

        return round(self.get_duration(), 2)

    def cancel_recording(self) -> None:
        """Discard recorded audio and reset state to IDLE."""
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

        with self._lock:
            self._recorded_chunks.clear()
            self._elapsed_seconds = 0.0

        self.state = self.STATE_IDLE
        if self.level_callback:
            self.level_callback(0.0)

    def get_duration(self) -> float:
        """Get current recorded duration in seconds."""
        if self.state == self.STATE_RECORDING:
            current_chunk = time.time() - self._last_resume_time
            return self._elapsed_seconds + current_chunk
        return self._elapsed_seconds

    def save_to_file(self, output_path: Path) -> Path:
        """
        Save the captured audio chunks to a standard WAV file.
        Returns the saved file path.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with self._lock:
            if not self._recorded_chunks:
                raise AudioRecorderError("No audio data was captured. Recording was empty.")
            audio_data = np.concatenate(self._recorded_chunks, axis=0)

        # Check for absolute silence/zeros
        if np.max(np.abs(audio_data)) < 1e-5:
            # Still valid audio but very quiet or silent
            pass

        try:
            sf.write(
                str(output_path),
                audio_data,
                self.sample_rate,
                subtype=Config.AUDIO_SUBTYPE,
                format=Config.AUDIO_FORMAT,
            )
        except Exception as e:
            raise AudioRecorderError(f"Failed to save audio file to {output_path}: {str(e)}")

        self.state = self.STATE_IDLE
        return output_path

