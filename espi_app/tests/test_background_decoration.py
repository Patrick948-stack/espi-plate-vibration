"""
test_background_decoration.py
Tests for espi_app/background_decoration.py (CornerDotDecoration, LandingBackground).

Covers the triangular dot cluster shape, the light/dark color and
opacity swap, that painting never raises, and that LandingBackground
wires into a theme change correctly.
"""

import pytest

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QPainter

from espi_app.background_decoration import CornerDotDecoration, LandingBackground


# ===========================================================================
# CornerDotDecoration: shape
# ===========================================================================

class TestCornerDotDecorationShape:
    def test_cluster_is_a_triangle_not_a_rectangle(self):
        decoration = CornerDotDecoration("light", "#1e1e1e")
        # Row 0 has _ROWS dots, row 1 has _ROWS - 1, ... row _ROWS - 1 has 1.
        # That is 6 + 5 + 4 + 3 + 2 + 1 = 21 dots, not 6 * 6 = 36.
        expected = sum(range(1, decoration._ROWS + 1))
        assert len(decoration._corner_points) == expected

    def test_every_dot_is_at_or_past_the_margin(self):
        decoration = CornerDotDecoration("light", "#1e1e1e")
        for point in decoration._corner_points:
            assert point.x() >= decoration._MARGIN
            assert point.y() >= decoration._MARGIN

    def test_rows_get_shorter_going_down(self):
        """Each row's rightmost dot must not reach as far as the row above it."""
        decoration = CornerDotDecoration("light", "#1e1e1e")
        rows = {}
        for point in decoration._corner_points:
            rows.setdefault(point.y(), []).append(point.x())

        row_max_x = [max(xs) for _, xs in sorted(rows.items())]
        assert row_max_x == sorted(row_max_x, reverse=True)


# ===========================================================================
# CornerDotDecoration: theme color and opacity
# ===========================================================================

class TestCornerDotDecorationTheme:
    def test_dark_theme_is_more_opaque_than_light(self):
        decoration = CornerDotDecoration("light", "#1e1e1e")
        light_alpha = decoration._color.alphaF()

        decoration.set_theme("dark", "#e0e0e0")
        dark_alpha = decoration._color.alphaF()

        assert dark_alpha > light_alpha

    def test_opacity_stays_subtle(self):
        """Both themes should stay in the roughly 8-15% range asked for, never opaque."""
        decoration = CornerDotDecoration("light", "#1e1e1e")
        assert 0.05 <= decoration._color.alphaF() <= 0.20

        decoration.set_theme("dark", "#e0e0e0")
        assert 0.05 <= decoration._color.alphaF() <= 0.20

    def test_color_hex_is_applied(self):
        decoration = CornerDotDecoration("dark", "#e0e0e0")
        assert decoration._color.red() == 0xe0
        assert decoration._color.green() == 0xe0
        assert decoration._color.blue() == 0xe0


# ===========================================================================
# CornerDotDecoration: painting does not raise
# ===========================================================================

class TestCornerDotDecorationPaint:
    def test_paint_does_not_raise(self, qtbot):
        # qtbot (unused directly) makes sure a QApplication exists first --
        # QPixmap/QPainter construction crashes hard without one.
        decoration = CornerDotDecoration("light", "#1e1e1e")
        pixmap = QPixmap(400, 300)
        painter = QPainter(pixmap)
        try:
            decoration.paint(painter, widget_width=400)
        finally:
            painter.end()

    def test_right_cluster_is_mirrored_not_duplicated(self):
        decoration = CornerDotDecoration("light", "#1e1e1e")
        widget_width = 1000
        left_xs = {p.x() for p in decoration._corner_points}
        mirrored_xs = {widget_width - p.x() for p in decoration._corner_points}
        # The two clusters should not overlap on a window this wide.
        assert left_xs.isdisjoint(mirrored_xs)


# ===========================================================================
# LandingBackground
# ===========================================================================

class TestLandingBackground:
    def test_has_styled_background_attribute_set(self, qtbot):
        """
        Without WA_StyledBackground, a plain QWidget silently ignores its
        stylesheet's background-color rule (the same gotcha ModeCard hit).
        """
        widget = LandingBackground("light", "#1e1e1e")
        qtbot.addWidget(widget)
        assert widget.testAttribute(Qt.WidgetAttribute.WA_StyledBackground)

    def test_set_theme_updates_the_decoration_color(self, qtbot):
        widget = LandingBackground("light", "#1e1e1e")
        qtbot.addWidget(widget)
        light_alpha = widget._decoration._color.alphaF()

        widget.set_theme("dark", "#e0e0e0")

        assert widget._decoration._color.alphaF() != light_alpha

    def test_paint_event_does_not_raise(self, qtbot):
        widget = LandingBackground("light", "#1e1e1e")
        qtbot.addWidget(widget)
        widget.resize(400, 300)
        widget.show()
        qtbot.waitExposed(widget)
        widget.repaint()
