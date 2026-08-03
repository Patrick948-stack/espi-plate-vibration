"""
logo_preview.py
Standalone logo preview tool for ESPI Camera System.

Run with: python3 logo_preview.py

Shows the logo in both light and dark modes, so you can iterate on the design
before integrating it into the main application.
"""

import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtGui import QPainter, QPen, QColor, QFont
from PyQt6.QtCore import Qt


class ESPILogo(QWidget):
    """
    Renders the ESPI logo as concentric circles with measurement axis.
    Configurable size, theme, and style parameters.
    """

    def __init__(self, theme_name="dark", size_px=200, parent=None):
        super().__init__(parent)
        self.theme_name = theme_name
        self.size_px = size_px
        self.setFixedSize(size_px, size_px)
        self.set_background()

    def set_background(self):
        """Set background color based on theme."""
        if self.theme_name == "light":
            self.setStyleSheet("background-color: #e8e8e8;")
        else:
            self.setStyleSheet("background-color: #1e1e1e;")

    def _get_stroke_color(self):
        """Return stroke color based on theme."""
        if self.theme_name == "light":
            return QColor("#0084d1")  # Professional blue
        else:
            return QColor("#00d4ff")  # Cyan

    def paintEvent(self, event):
        """Draw the logo using QPainter."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        center_x = self.size_px / 2
        center_y = self.size_px / 2
        stroke_color = self._get_stroke_color()

        # ========== Draw Concentric Circles ==========
        pen = QPen(stroke_color)
        pen.setWidth(3)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)

        # Four concentric circles (outer to inner)
        # Adjust these radii to change the spacing
        circle_radii = [80, 64, 48, 32]

        for radius in circle_radii:
            painter.drawEllipse(
                int(center_x - radius),
                int(center_y - radius),
                radius * 2,
                radius * 2
            )

        # ========== Draw Vertical Measurement Axis ==========
        pen.setWidth(2.5)
        painter.setPen(pen)

        # Vertical line through center (measurement axis)
        axis_length = 100
        painter.drawLine(
            int(center_x), int(center_y - axis_length / 2),
            int(center_x), int(center_y + axis_length / 2)
        )

        # ========== Draw Measurement Points ==========
        # Top measurement point (larger circle)
        painter.drawEllipse(
            int(center_x - 5), int(center_y - axis_length / 2 - 5),
            10, 10
        )

        # Center point (largest)
        painter.drawEllipse(
            int(center_x - 6), int(center_y - 6),
            12, 12
        )

        # Bottom measurement point (larger circle)
        painter.drawEllipse(
            int(center_x - 5), int(center_y + axis_length / 2 - 5),
            10, 10
        )

        painter.end()

    def set_theme(self, theme_name: str):
        """Update logo color and background when theme changes."""
        self.theme_name = theme_name
        self.set_background()
        self.update()  # Trigger repaint


class LogoPreviewWindow(QMainWindow):
    """Main window showing logo in both light and dark modes."""

    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        """Initialize the preview window."""
        self.setWindowTitle("ESPI Logo Preview - Edit Together")
        self.setGeometry(100, 100, 1000, 600)

        # Main widget and layout
        main_widget = QWidget()
        main_layout = QHBoxLayout()
        main_layout.setSpacing(40)
        main_layout.setContentsMargins(40, 40, 40, 40)

        # ========== DARK MODE SECTION ==========
        dark_container = QWidget()
        dark_layout = QVBoxLayout()
        dark_layout.setSpacing(16)

        dark_title = QLabel("DARK MODE")
        dark_title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        dark_title.setStyleSheet("color: #e0e0e0; background-color: #1e1e1e; padding: 10px;")
        dark_layout.addWidget(dark_title)

        self.dark_logo = ESPILogo(theme_name="dark", size_px=300)
        dark_layout.addWidget(self.dark_logo, alignment=Qt.AlignmentFlag.AlignCenter)

        dark_info = QLabel(
            "Cyan: #00d4ff\n"
            "Size: 200px (main app)\n"
            "Stroke width: 3px"
        )
        dark_info.setStyleSheet("color: #8a8a8a; background-color: #1e1e1e; padding: 10px; font-size: 11px;")
        dark_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dark_layout.addWidget(dark_info)

        dark_container.setLayout(dark_layout)
        dark_container.setStyleSheet("background-color: #1e1e1e;")

        # ========== LIGHT MODE SECTION ==========
        light_container = QWidget()
        light_layout = QVBoxLayout()
        light_layout.setSpacing(16)

        light_title = QLabel("LIGHT MODE")
        light_title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        light_title.setStyleSheet("color: #1e1e1e; background-color: #e8e8e8; padding: 10px;")
        light_layout.addWidget(light_title)

        self.light_logo = ESPILogo(theme_name="light", size_px=300)
        light_layout.addWidget(self.light_logo, alignment=Qt.AlignmentFlag.AlignCenter)

        light_info = QLabel(
            "Blue: #0084d1\n"
            "Size: 200px (main app)\n"
            "Stroke width: 3px"
        )
        light_info.setStyleSheet("color: #5a5a5a; background-color: #e8e8e8; padding: 10px; font-size: 11px;")
        light_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        light_layout.addWidget(light_info)

        light_container.setLayout(light_layout)
        light_container.setStyleSheet("background-color: #e8e8e8;")

        # Add sections to main layout
        main_layout.addWidget(dark_container)
        main_layout.addWidget(light_container)

        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)


def main():
    """Run the logo preview."""
    app = QApplication(sys.argv)
    window = LogoPreviewWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
