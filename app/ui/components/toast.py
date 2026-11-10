"""ToastNotification component for non-blocking feedback messages."""
from PySide6.QtWidgets import QWidget, QLabel, QHBoxLayout
from PySide6.QtCore import Qt, QTimer


class ToastNotification(QWidget):
    """Subtle status toast for user notifications."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.SubWindow | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)

        self.label = QLabel("")
        self.label.setStyleSheet("color: #FFFFFF; font-weight: 500; font-size: 13px; background: transparent;")
        layout.addWidget(self.label)

        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.hide)

        self.hide()

    def show_message(self, message: str, is_error: bool = False, duration_ms: int = 3500):
        self.label.setText(message)
        bg_color = "#E53E3E" if is_error else "#344C59"
        self.setStyleSheet(f"""
            ToastNotification {{
                background-color: {bg_color};
                border-radius: 8px;
            }}
        """)
        self.adjustSize()

        if self.parent():
            p_geom = self.parent().geometry()
            x = (p_geom.width() - self.width()) // 2
            y = p_geom.height() - self.height() - 40
            self.move(x, y)

        self.show()
        self.raise_()
        self.hide_timer.start(duration_ms)

