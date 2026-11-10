"""MoodBadge component displaying mood status pills."""
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PySide6.QtCore import Qt
from app.services.mood_service import MoodService


class MoodBadge(QWidget):
    """Pill-shaped badge displaying mood name with soft tinted background and indicator dot."""

    # Muted background & text color palette for calming aesthetics
    MOOD_STYLES = {
        "Happy": {"bg": "#EAF0E5", "fg": "#506344", "dot": "#81956F"},
        "Excited": {"bg": "#F5EEE4", "fg": "#8F6740", "dot": "#B88952"},
        "Calm": {"bg": "#EAF0EF", "fg": "#486761", "dot": "#718F87"},
        "Grateful": {"bg": "#F0ECF4", "fg": "#665B7D", "dot": "#9A8BB8"},
        "Neutral": {"bg": "#F1F0ED", "fg": "#62636B", "dot": "#8B8C92"},
        "Stressed": {"bg": "#F5EDEA", "fg": "#8A5E55", "dot": "#AD776B"},
        "Sad": {"bg": "#ECEDEF", "fg": "#535763", "dot": "#737985"},
        "Frustrated": {"bg": "#F5E9E7", "fg": "#8B4E4C", "dot": "#B16E67"},
        "Mixed": {"bg": "#F3EAF0", "fg": "#805A73", "dot": "#AB8099"},
        "Uncertain": {"bg": "#EEEDF3", "fg": "#665F7D", "dot": "#8A80A8"},
    }

    def __init__(self, mood: str = "Neutral", parent=None):
        super().__init__(parent)
        self.mood = mood or "Neutral"
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 12, 4)
        layout.setSpacing(6)

        style = self.MOOD_STYLES.get(self.mood, self.MOOD_STYLES["Neutral"])

        self.dot_label = QLabel("●")
        self.dot_label.setStyleSheet(f"color: {style['dot']}; font-size: 10px; background: transparent; border: none;")

        self.text_label = QLabel(self.mood)
        self.text_label.setStyleSheet(
            f"color: {style['fg']}; font-weight: 600; font-size: 11px; background: transparent; border: none;"
        )

        layout.addWidget(self.dot_label)
        layout.addWidget(self.text_label)
        layout.setAlignment(Qt.AlignCenter)

        self.setStyleSheet(
            f"MoodBadge {{ background-color: {style['bg']}; border-radius: 12px; border: 1px solid {style['bg']}; }}"
        )

    def set_mood(self, mood: str):
        self.mood = mood or "Neutral"
        style = self.MOOD_STYLES.get(self.mood, self.MOOD_STYLES["Neutral"])
        self.dot_label.setStyleSheet(f"color: {style['dot']}; font-size: 10px; background: transparent; border: none;")
        self.text_label.setText(self.mood)
        self.text_label.setStyleSheet(
            f"color: {style['fg']}; font-weight: 600; font-size: 11px; background: transparent; border: none;"
        )
        self.setStyleSheet(
            f"MoodBadge {{ background-color: {style['bg']}; border-radius: 12px; border: 1px solid {style['bg']}; }}"
        )
