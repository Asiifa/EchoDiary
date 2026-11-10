"""AudioWaveformVisualizer widget showing animated level bars during recording and playback."""
import random
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtGui import QPainter, QColor, QBrush, QPen


class AudioWaveformVisualizer(QWidget):
    """
    Renders dynamic, calming audio level bars that react to microphone input
    or playback with smooth easing and falloff decay.
    """

    def __init__(self, num_bars: int = 36, parent=None):
        super().__init__(parent)
        self.num_bars = num_bars
        self.bar_heights = [0.1] * num_bars
        self.target_heights = [0.1] * num_bars
        self.is_active = False

        self.setMinimumHeight(64)
        self.setMaximumHeight(80)

        # Timer for smooth frame rendering and decay
        self.decay_timer = QTimer(self)
        self.decay_timer.timeout.connect(self._animate_decay)
        self.decay_timer.start(30)  # ~33 fps

    @Slot(float)
    def update_level(self, level: float):
        """Update live audio level (0.0 to 1.0)."""
        self.is_active = (level > 0.02)

        # Distribute energy across bars with natural organic variance
        for i in range(self.num_bars):
            # Center bars tend to be slightly taller
            center_dist = abs(i - (self.num_bars / 2.0)) / (self.num_bars / 2.0)
            center_weight = 1.0 - (0.35 * center_dist)

            jitter = random.uniform(0.7, 1.3)
            h = min(1.0, max(0.08, level * center_weight * jitter))
            self.target_heights[i] = h

        self.update()

    def _animate_decay(self):
        """Smoothly interpolate bar heights towards targets with decay."""
        changed = False
        for i in range(self.num_bars):
            diff = self.target_heights[i] - self.bar_heights[i]
            if abs(diff) > 0.005:
                self.bar_heights[i] += diff * 0.25
                changed = True
            # Decay target gradually when silence
            self.target_heights[i] = max(0.08, self.target_heights[i] * 0.88)

        if changed:
            self.update()

    def reset(self):
        """Reset bars to baseline idle state."""
        self.is_active = False
        self.target_heights = [0.08] * self.num_bars
        self.bar_heights = [0.08] * self.num_bars
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        spacing = 4
        bar_w = max(3.0, (w - (self.num_bars * spacing)) / float(self.num_bars))

        center_y = h / 2.0

        for i in range(self.num_bars):
            x = i * (bar_w + spacing)
            bar_pct = self.bar_heights[i]
            bar_h = max(4.0, bar_pct * (h - 16))

            y = center_y - (bar_h / 2.0)

            if self.is_active:
                # Soft lavender gradient/color
                color = QColor(154, 139, 184, int(160 + (bar_pct * 95)))
            else:
                # Subtle neutral gray
                color = QColor(197, 196, 192, 140)

            painter.setBrush(QBrush(color))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(x, y, bar_w, bar_h, 2.0, 2.0)
