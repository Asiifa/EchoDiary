"""Summary service providing abstraction for daily 3-line summaries."""
from typing import List
from app.services.ollama_service import OllamaService


class SummaryService:
    """Manages generation and validation of 3-line summaries."""

    def __init__(self, ollama_service: OllamaService = None):
        self.ollama = ollama_service or OllamaService()

    def generate_summary(self, transcript: str, entry_date: str) -> List[str]:
        """Generate exactly three summary sentences for a diary transcript."""
        analysis = self.ollama.analyze_daily_entry(transcript, entry_date)
        return analysis.summary

