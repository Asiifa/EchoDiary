"""Mood analysis service."""
from typing import Dict, Any, List
from app.services.ollama_service import OllamaService
from app.config import Config


class MoodService:
    """Manages mood extraction, confidence estimation, and category tracking."""

    @staticmethod
    def get_supported_moods() -> List[str]:
        return Config.SUPPORTED_MOODS

    @staticmethod
    def get_mood_color(mood: str) -> str:
        """Return hex color code associated with mood for badges and charts."""
        colors = {
            "Happy": "#48BB78",       # Fresh Green
            "Excited": "#ECC94B",     # Warm Gold
            "Calm": "#4FD1C5",        # Soft Teal
            "Grateful": "#9F7AEA",    # Lavender Purple
            "Neutral": "#A0AEC0",    # Slate Gray
            "Stressed": "#ED8936",   # Warm Orange
            "Sad": "#4299E1",         # Muted Blue
            "Frustrated": "#F56565",  # Coral Red
            "Mixed": "#ED64A6",       # Pink
            "Uncertain": "#805AD5",   # Deep Purple
        }
        return colors.get(mood, "#A0AEC0")

