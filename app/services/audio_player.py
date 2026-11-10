"""Audio playback service using soundfile and sounddevice."""
import time
import threading
from pathlib import Path
from typing import Optional, Callable
import numpy as np
import sounddevice as sd
import soundfile as sf


class AudioPlayerError(Exception):
    """Exception raised for audio playback issues."""
    pass


class AudioPlayer:
    """
    Threaded, non-blocking audio player supporting play, pause, resume,
    stop, seek, and real-time playback position callbacks.
    """

    STATE_STOPPED = "STOPPED"
    STATE_PLAYING = "PLAYING"
    STATE_PAUSED = "PAUSED"

    def __init__(
        self,
        position_callback: Optional[Callable[[float, float], None]] = None,
        finished_callback: Optional[Callable[[], None]] = None,
    ):
        self.position_callback = position_callback
        self.finished_callback = finished_callback

        self.state = self.STATE_STOPPED
        self.audio_data: Optional[np.ndarray] = None
        self.samplerate: int = 44100
        self.channels: int = 1
        self.duration: float = 0.0

        self.current_frame: int = 0
        self._stream: Optional[sd.OutputStream] = None
        self._lock = threading.Lock()
        self._file_path: Optional[str] = None

    def load(self, file_path: str) -> float:
        """Load an audio file into memory and return its duration in seconds."""
        self.stop()
        path = Path(file_path)
        if not path.exists():
            raise AudioPlayerError(f"Audio file not found: {file_path}")

        try:
            data, sr = sf.read(str(path), dtype="float32")
            if data.ndim == 1:
                channels = 1
            else:
                channels = data.shape[1]

            with self._lock:
                self.audio_data = data
                self.samplerate = sr
                self.channels = channels
                self.duration = len(data) / float(sr)
                self.current_frame = 0
                self._file_path = str(path)
            return self.duration
        except Exception as e:
            raise AudioPlayerError(f"Failed to load audio for playback: {str(e)}")

    def _stream_callback(self, outdata: np.ndarray, frames: int, time_info: any, status: sd.CallbackFlags) -> None:
        """Sounddevice output stream callback."""
        with self._lock:
            if self.audio_data is None or self.state != self.STATE_PLAYING:
                outdata.fill(0)
                return

            remaining_frames = len(self.audio_data) - self.current_frame
            if remaining_frames <= 0:
                outdata.fill(0)
                # Signal completion
                self.state = self.STATE_STOPPED
                self.current_frame = 0
                if self.finished_callback:
                    threading.Thread(target=self.finished_callback, daemon=True).start()
                raise sd.CallbackStop

            chunk_size = min(frames, remaining_frames)
            chunk = self.audio_data[self.current_frame: self.current_frame + chunk_size]

            if chunk.ndim == 1 and outdata.ndim == 2:
                # Mono to output channels
                for c in range(outdata.shape[1]):
                    outdata[:chunk_size, c] = chunk
            elif chunk.ndim == 2 and outdata.ndim == 2:
                outdata[:chunk_size, :chunk.shape[1]] = chunk
            else:
                outdata[:chunk_size] = chunk

            if chunk_size < frames:
                outdata[chunk_size:].fill(0)

            self.current_frame += chunk_size
            current_sec = self.current_frame / float(self.samplerate)

        if self.position_callback:
            try:
                self.position_callback(min(current_sec, self.duration), self.duration)
            except Exception:
                pass

    def play(self, from_start: bool = False) -> None:
        """Start or resume playback."""
        with self._lock:
            if self.audio_data is None:
                raise AudioPlayerError("No audio file loaded.")

            if from_start:
                self.current_frame = 0

            if self.state == self.STATE_PLAYING:
                return

        self.stop_stream_only()

        with self._lock:
            self.state = self.STATE_PLAYING

        try:
            self._stream = sd.OutputStream(
                samplerate=self.samplerate,
                channels=min(self.channels, 2),
                callback=self._stream_callback,
                finished_callback=self._on_stream_finished,
            )
            self._stream.start()
        except Exception as e:
            self.state = self.STATE_STOPPED
            raise AudioPlayerError(f"Failed to start audio playback stream: {str(e)}")

    def pause(self) -> None:
        """Pause audio playback."""
        with self._lock:
            if self.state == self.STATE_PLAYING:
                self.state = self.STATE_PAUSED
        self.stop_stream_only()

    def resume(self) -> None:
        """Resume playback from current position."""
        if self.state == self.STATE_PAUSED:
            self.play(from_start=False)

    def stop(self) -> None:
        """Stop playback and reset position to 0."""
        with self._lock:
            self.state = self.STATE_STOPPED
            self.current_frame = 0
        self.stop_stream_only()
        if self.position_callback and self.duration > 0:
            try:
                self.position_callback(0.0, self.duration)
            except Exception:
                pass

    def seek(self, target_seconds: float) -> None:
        """Seek to a specific time position in seconds."""
        with self._lock:
            if self.audio_data is None:
                return
            target_frame = int(np.clip(target_seconds * self.samplerate, 0, len(self.audio_data)))
            self.current_frame = target_frame
            current_sec = self.current_frame / float(self.samplerate)

        if self.position_callback:
            try:
                self.position_callback(current_sec, self.duration)
            except Exception:
                pass

    def stop_stream_only(self) -> None:
        """Safely close active audio output stream without resetting position."""
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

    def _on_stream_finished(self) -> None:
        """Callback when sounddevice finishes stream."""
        pass

