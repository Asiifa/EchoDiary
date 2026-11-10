"""StatCard component for dashboard metric indicators."""
from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel
from PySide6.QtCore import Qt


class StatCard(QFrame):
    """Clean metric card with upper title, large numerical counter, and descriptive footer."""

    def __init__(self, title: str, value: str = "0", subtext: str = "", accent_color: str = "#9A8BB8", parent=None):
        super().__init__(parent)
        self.setObjectName("StatCard")
        self.accent_color = accent_color
        self._init_ui(title, value, subtext)

    def _init_ui(self, title: str, value: str, subtext: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(4)

        self.title_label = QLabel(title.upper())
        self.title_label.setObjectName("StatTitle")
        self.title_label.setStyleSheet("color: #777985; font-size: 11px; font-weight: 600; letter-spacing: 0.5px;")

        self.value_label = QLabel(str(value))
        self.value_label.setObjectName("StatValue")
        self.value_label.setStyleSheet(
            f"color: {self.accent_color}; font-size: 28px; font-weight: 700; margin-top: 2px;"
        )

        self.subtext_label = QLabel(subtext)
        self.subtext_label.setObjectName("StatSubtext")
        self.subtext_label.setStyleSheet("color: #96979E; font-size: 11px; margin-top: 2px;")

        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        layout.addWidget(self.subtext_label)

        self.setStyleSheet("""
            QFrame#StatCard {
                background-color: #FFFFFF;
                border: 1px solid #E5E2DE;
                border-radius: 12px;
            }
        """)

    def set_value(self, value: str):
        self.value_label.setText(str(value))

    def set_subtext(self, subtext: str):
        self.subtext_label.setText(subtext)

