"""
background_decoration.py

A subtle, purely decorative dot pattern painted in the top-left and
top-right corners of the landing page background. Drawn with QPainter
inside paintEvent (no image or SVG assets), so it stays lightweight,
scales cleanly on high-DPI displays, and can recolor itself instantly
on a theme change instead of needing a new asset per theme.
"""

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import QWidget


class CornerDotDecoration:
    """
    Computes and paints two dot clusters, one per top corner, each an
    inverted triangle: the top row has the most dots, and each row below
    it has one fewer, so the cluster narrows as it moves away from its
    corner toward the center of the window.

    The dot positions for one corner are computed once, in __init__, and
    reused for both corners (the right corner is just the left pattern
    mirrored across the window's current width at paint time) and across
    every repaint, so paint() itself only does cheap drawing, no layout
    math beyond one subtraction per dot.
    """

    _ROWS = 6  # dots in the top row; each row below has one fewer
    _DOT_DIAMETER = 2.6
    _SPACING = 15  # both between dots in a row and between rows
    _MARGIN = 28  # distance from the corner to the first dot

    def __init__(self, theme_name: str, color_hex: str):
        self._dot_radius = self._DOT_DIAMETER / 2
        self._corner_points = self._build_corner_cluster()
        self.set_theme(theme_name, color_hex)

    def _build_corner_cluster(self):
        """
        Dot centers for one corner's cluster, anchored to that corner's
        own (0, 0). Row 0 (the top row) has _ROWS dots; each following
        row has one fewer, which is what makes the cluster read as an
        inverted triangle instead of a plain rectangle of dots.
        """
        points = []
        for row in range(self._ROWS):
            dots_in_row = self._ROWS - row
            y = self._MARGIN + row * self._SPACING
            for col in range(dots_in_row):
                x = self._MARGIN + col * self._SPACING
                points.append(QPointF(x, y))
        return points

    def set_theme(self, theme_name: str, color_hex: str):
        """
        Recolor the dots for a theme change. Does not trigger a repaint
        itself; the caller (LandingBackground.set_theme) does that.
        """
        normalized = "dark" if theme_name.lower() == "dark" else "light"
        opacity = 0.12 if normalized == "dark" else 0.10
        color = QColor(color_hex)
        color.setAlphaF(opacity)
        self._color = color

    def paint(self, painter: QPainter, widget_width: int):
        """Paint both corner clusters. widget_width mirrors the left cluster into the right corner."""
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._color)

        for point in self._corner_points:
            painter.drawEllipse(point, self._dot_radius, self._dot_radius)

        for point in self._corner_points:
            mirrored = QPointF(widget_width - point.x(), point.y())
            painter.drawEllipse(mirrored, self._dot_radius, self._dot_radius)

        painter.restore()


class LandingBackground(QWidget):
    """
    The landing page's central widget. Paints the shared theme's
    background (via the stylesheet, same as every other window) and then
    the corner dot decoration on top of it, before any child widget
    (logo, cards, buttons) is painted on top of both -- Qt always paints
    a widget's own paintEvent before its children's, so this keeps the
    dots strictly in the background layer without touching the layout.
    """

    def __init__(self, theme_name: str, color_hex: str, parent=None):
        super().__init__(parent)
        # A plain QWidget does not paint background-color from a
        # stylesheet unless this is set (see mode_card.py for the same
        # gotcha) -- without it the QSS "QMainWindow, QWidget" rule would
        # be silently ignored here.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._decoration = CornerDotDecoration(theme_name, color_hex)

    def set_theme(self, theme_name: str, color_hex: str):
        """Recolor the dots for a theme change and repaint."""
        self._decoration.set_theme(theme_name, color_hex)
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)  # stylesheet background first
        painter = QPainter(self)
        self._decoration.paint(painter, self.width())
        painter.end()
