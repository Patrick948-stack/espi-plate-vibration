"""
logo.py

The ESPI logo, loaded from the vector asset espi_app/logo.svg (a camera
aperture / interference emblem) instead of the previous hand-drawn
QPainter concentric-circle shape.

Rendering approach and why it isn't a bare QSvgWidget:
    logo.svg is a real multi-tone grayscale graphic (roughly 900 paths,
    shaded from black through many shades of gray to near-white) rather
    than a simple flat-color line icon, and its very first path is an
    opaque square filling the whole canvas edge-to-edge (not a transparent
    background around a circular emblem). A plain QSvgWidget just
    displays whatever is baked into the file as-is: a hard-edged square
    "sticker" rather than a floating icon. A single-hue
    QGraphicsColorizeEffect (Qt's usual "recolor a widget" tool) can't
    invert lightness or add transparency either, so it would not fix
    either problem.

    Instead, the SVG is rasterized once with QSvgRenderer (still the
    real Qt SVG framework, not hand-rolled trigonometry), then a circular
    mask is applied so the square corners become transparent -- letting
    it float on the page like the rest of this app's icons instead of
    sitting in a hard-edged box. Two versions of that masked circle are
    kept: the artwork as authored (a dark background behind a bright
    center pattern) and an RGB-inverted copy (a light background behind
    a dark center pattern, alpha/transparency untouched so the circular
    mask still applies). Each is shown on whichever theme its own
    background blends into -- the dark-background version on the dark
    theme, the inverted light-background version on the light theme --
    so swapping is just picking which pixmap to show, no redraw math at
    all, on the rare occasions the theme actually changes.
"""

import sys
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QImage, QPainter, QPainterPath, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QLabel


def _resource_dir() -> Path:
    """
    Where to find bundled data files like logo.svg.

    Running from source, that is just this file's own folder. Running as
    a PyInstaller-frozen app (packaging/ESPI.spec, .github/workflows/
    build-windows.yml), it is the temp folder PyInstaller extracts bundled
    data files into at startup (sys._MEIPASS), under an "espi_app"
    subfolder matching where the build declares logo.svg should be
    copied to. Without this check, a frozen build looks for logo.svg at
    this source file's own on-disk path, which does not exist inside the
    frozen bundle: real bug, found while chasing a separate report that
    the Windows taskbar icon did not show while the app was open. logo.svg
    was never declared as a PyInstaller data file at all, so ESPILogo
    (the on-screen logo used on the landing page and every dashboard title
    bar) would have silently rendered blank in every packaged build so far.
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "espi_app"
    return Path(__file__).resolve().parent


_SVG_PATH = _resource_dir() / "logo.svg"

# Rendered at a higher resolution than the on-screen size so the logo
# stays crisp on high-DPI (Retina) displays, then scaled down for display.
_RENDER_SCALE = 3


def _render_circular_masked(svg_path: Path, render_size: int) -> QImage:
    """Rasterize svg_path, then clip everything outside an inscribed circle to transparent."""
    renderer = QSvgRenderer(str(svg_path))
    image = QImage(render_size, render_size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)

    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    circle = QPainterPath()
    circle.addEllipse(0, 0, render_size, render_size)
    painter.setClipPath(circle)
    renderer.render(painter)
    painter.end()
    return image


class ESPILogo(QLabel):
    """Displays espi_app/logo.svg as a floating circular badge, inverted for dark theme."""

    def __init__(self, theme_name: str, size_px: int = 100, parent=None):
        super().__init__(parent)
        self.setFixedSize(size_px, size_px)
        self._size_px = size_px

        image = _render_circular_masked(_SVG_PATH, size_px * _RENDER_SCALE)
        # As-authored: dark background, bright center -- shown on the dark
        # theme so the dark background blends into the window.
        self._dark_bg_pixmap = QPixmap.fromImage(image)

        # RGB-inverted: light background, dark center -- shown on the
        # light theme for the same blending reason, in reverse.
        inverted = image.copy()
        inverted.invertPixels(QImage.InvertMode.InvertRgb)
        self._light_bg_pixmap = QPixmap.fromImage(inverted)

        self.set_theme(theme_name)

    def set_theme(self, theme_name: str):
        """Swap to the dark- or light-background pixmap and repaint immediately."""
        pixmap = self._dark_bg_pixmap if theme_name.lower() == "dark" else self._light_bg_pixmap
        self.setPixmap(pixmap.scaled(
            self._size_px, self._size_px,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        ))


def build_icon() -> QIcon:
    """
    Build a QIcon from the same circular-masked logo.svg rendering used
    everywhere else (ESPILogo above, packaging/generate_icons.py's file
    icons), for QApplication.setWindowIcon().

    Why this is needed: PyInstaller's --icon build flag only sets the
    built .exe/.app FILE's own icon, the one Explorer/Finder shows before
    the app is even running. It does not set the RUNNING window's taskbar
    icon on Windows; Qt only picks that up from an explicit
    setWindowIcon() call, which nothing in this app made before. That is
    exactly why the Windows taskbar showed a generic icon while the app
    was open, even though the file icon (and the Mac dock icon, which
    Cocoa does default to the bundle icon for automatically, unlike
    Windows) were both already correct.
    """
    image = _render_circular_masked(_SVG_PATH, 256)
    return QIcon(QPixmap.fromImage(image))
