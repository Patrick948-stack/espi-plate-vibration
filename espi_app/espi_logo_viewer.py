"""
espi_logo_viewer.py

Standalone viewer for the ESPI logo. Run with:
    python3 espi_logo_viewer.py

Features a toggle button to switch between light and dark backgrounds,
and displays the logo at multiple sizes to verify scalability.
"""

import sys
import math
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter, QPen, QBrush
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QPushButton, QHBoxLayout


class ESPILogo(QWidget):
    """Draws the ESPI logo using QPainter.

    Design: concentric rings representing wavefronts and interference patterns,
    with a central aperture and subtle radial phase interruptions.
    """

    def __init__(self, size_px: int = 200, dark_background: bool = False, parent=None):
        super().__init__(parent)
        self.size_px = size_px
        self.dark_background = dark_background
        self.setFixedSize(size_px, size_px)

    def set_dark_background(self, dark: bool):
        """Toggle between dark and light backgrounds."""
        self.dark_background = dark
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background
        bg_color = QColor(30, 30, 30) if self.dark_background else QColor(255, 255, 255)
        stroke_color = QColor(255, 255, 255) if self.dark_background else QColor(0, 0, 0)
        painter.fillRect(self.rect(), bg_color)

        center_x = self.size_px / 2
        center_y = self.size_px / 2
        scale = self.size_px / 200.0  # Design for 200px base

        # Draw the logo components
        self._draw_interference_rings(painter, center_x, center_y, scale, stroke_color)
        self._draw_central_aperture(painter, center_x, center_y, scale, stroke_color)
        self._draw_phase_interruptions(painter, center_x, center_y, scale, stroke_color)

        painter.end()

    def _draw_interference_rings(self, painter, cx, cy, scale, stroke_color):
        """Draw concentric circular rings representing wavefronts."""

        # Ring definitions: (radius_px, stroke_width, opacity)
        rings = [
            (90, 3.0, 100),   # Outermost ring, full opacity
            (70, 2.5, 90),    # Strong secondary ring
            (50, 2.0, 80),    # Medium ring
            (30, 2.0, 70),    # Inner ring
        ]

        for radius, stroke_width, opacity in rings:
            pen = QPen(stroke_color)
            pen.setWidthF(stroke_width * scale)

            # Adjust color opacity
            color = QColor(stroke_color)
            color.setAlpha(int(opacity * 2.55))  # Convert 0-100 to 0-255
            pen.setColor(color)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)

            painter.setPen(pen)
            r = radius * scale
            painter.drawEllipse(int(cx - r), int(cy - r), int(r * 2), int(r * 2))

    def _draw_central_aperture(self, painter, cx, cy, scale, stroke_color):
        """Draw central circular aperture (lens element)."""

        # Inner aperture circle with subtle fill
        aperture_radius = 15 * scale

        # Light fill to suggest depth and lens material
        fill_color = QColor(stroke_color)
        if self.dark_background:
            fill_color = QColor(80, 80, 80)
        else:
            fill_color = QColor(240, 240, 240)

        brush = QBrush(fill_color)
        painter.setBrush(brush)

        pen = QPen(stroke_color)
        pen.setWidthF(1.5 * scale)
        painter.setPen(pen)

        painter.drawEllipse(
            int(cx - aperture_radius), int(cy - aperture_radius),
            int(aperture_radius * 2), int(aperture_radius * 2)
        )

        # Center point dot (focus point)
        dot_radius = 2.5 * scale
        painter.drawEllipse(
            int(cx - dot_radius), int(cy - dot_radius),
            int(dot_radius * 2), int(dot_radius * 2)
        )

    def _draw_phase_interruptions(self, painter, cx, cy, scale, stroke_color):
        """Draw subtle radial interruptions suggesting light interference.

        These are small phase shifts at cardinal and diagonal directions,
        breaking the perfect continuity of the rings to suggest wave interference.
        """

        # Angles for phase interruptions: cardinal + diagonal directions
        angles = [0, 45, 90, 135, 180, 225, 270, 315]

        # Draw small arc interruptions on the outer ring
        outer_ring_radius = 90 * scale
        interruption_length = 12 * scale
        interruption_width = 1.8 * scale

        pen = QPen(stroke_color)
        pen.setWidthF(interruption_width)

        # Alternate color opacity to create subtle visual rhythm
        color = QColor(stroke_color)
        color.setAlpha(150)
        pen.setColor(color)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)

        painter.setPen(pen)

        for i, angle_deg in enumerate(angles):
            angle_rad = math.radians(angle_deg)

            # Start point on the outer ring
            x1 = cx + outer_ring_radius * math.cos(angle_rad)
            y1 = cy + outer_ring_radius * math.sin(angle_rad)

            # End point, extending outward
            x2 = cx + (outer_ring_radius + interruption_length) * math.cos(angle_rad)
            y2 = cy + (outer_ring_radius + interruption_length) * math.sin(angle_rad)

            painter.drawLine(int(x1), int(y1), int(x2), int(y2))


class ESPILogoViewer(QMainWindow):
    """Main window for viewing the ESPI logo at multiple scales."""

    def __init__(self):
        super().__init__()
        self.dark_mode = False
        self.setWindowTitle("ESPI Logo Viewer")
        self.setGeometry(100, 100, 1000, 800)

        # Central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Top controls
        controls_layout = QHBoxLayout()

        toggle_btn = QPushButton("Toggle Dark Background")
        toggle_btn.clicked.connect(self._toggle_dark_mode)
        controls_layout.addWidget(toggle_btn)
        controls_layout.addStretch()

        layout.addLayout(controls_layout)

        # Logo display at multiple sizes
        sizes_layout = QHBoxLayout()

        for size in [100, 150, 200, 300]:
            container = QWidget()
            container_layout = QVBoxLayout(container)

            logo = ESPILogo(size_px=size, dark_background=self.dark_mode)
            self.logos = getattr(self, 'logos', [])
            self.logos.append(logo)

            container_layout.addWidget(logo, alignment=Qt.AlignmentFlag.AlignCenter)
            label = QPushButton(f"{size}px")
            label.setFlat(True)
            container_layout.addWidget(label, alignment=Qt.AlignmentFlag.AlignCenter)

            sizes_layout.addWidget(container)

        layout.addLayout(sizes_layout)
        layout.addStretch()

    def _toggle_dark_mode(self):
        """Toggle between dark and light backgrounds."""
        self.dark_mode = not self.dark_mode

        if hasattr(self, 'logos'):
            for logo in self.logos:
                logo.set_dark_background(self.dark_mode)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    viewer = ESPILogoViewer()
    viewer.show()
    sys.exit(app.exec())
