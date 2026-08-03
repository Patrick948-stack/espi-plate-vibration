"""
mode_card.py

The clickable "Monitor Mode" / "Scan Mode" card on the landing page: an
icon inside a circular badge, a bold title, a short divider mark, and a
two-line description, styled as a raised card with a drop shadow that
grows on hover.

A QPushButton can't show icon + title + a separate description line at
once (only one label), so this is a plain QWidget instead, with its own
clicked signal and press/release tracking to behave like a button.
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QLabel,
    QVBoxLayout,
    QWidget,
)
import qtawesome as qta


class ModeCard(QWidget):
    """
    A raised, clickable mode-selection card.

    Emits `clicked` on a left mouse press-then-release inside the card's
    bounds (mirroring QPushButton's own click semantics) — and, like any
    QWidget, automatically stops receiving mouse events at all once
    setEnabled(False) is called, so a disabled card is not clickable
    without any extra guard code needed here.
    """

    clicked = pyqtSignal()

    def __init__(self, icon_name: str, title_text: str, description_text: str,
                 icon_hex_color: str, badge_bg: str, divider_color: str, parent=None):
        super().__init__(parent)
        self.setObjectName("ModeCard")
        # A plain QWidget does not paint background-color/border from its
        # stylesheet by default (only QFrame and a few others do) --
        # without this attribute, the QSS below would be silently ignored.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumSize(240, 240)
        self._pressed = False

        layout = QVBoxLayout()
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # --- Icon, inside a circular badge ---
        self.icon_badge = QLabel()
        self.icon_badge.setObjectName("ModeCardBadge")
        self.icon_badge.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.icon_badge.setFixedSize(72, 72)
        self.icon_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge_row = QVBoxLayout()
        badge_row.setContentsMargins(0, 0, 0, 0)
        badge_row.addWidget(self.icon_badge, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addLayout(badge_row)
        layout.addSpacing(20)

        self.title_label = QLabel(title_text)
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label)
        layout.addSpacing(8)

        # --- Small divider mark between title and description ---
        divider = QFrame()
        divider.setFixedSize(20, 2)
        divider.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        divider.setStyleSheet(f"background-color: {divider_color}; border: none;")
        divider_row = QVBoxLayout()
        divider_row.setContentsMargins(0, 0, 0, 0)
        divider_row.addWidget(divider, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addLayout(divider_row)
        layout.addSpacing(8)

        self.description_label = QLabel(description_text)
        self.description_label.setObjectName("ModeCardDescription")
        self.description_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.description_label.setWordWrap(True)
        layout.addWidget(self.description_label)

        self.setLayout(layout)

        self._icon_name = icon_name
        self.set_colors(icon_hex_color, badge_bg)

        self._shadow = QGraphicsDropShadowEffect()
        self._default_blur, self._default_offset = 12, 4
        self._hover_blur, self._hover_offset = 22, 8
        self._shadow.setBlurRadius(self._default_blur)
        self._shadow.setOffset(0, self._default_offset)
        self.setGraphicsEffect(self._shadow)

    def set_colors(self, icon_hex_color: str, badge_bg: str):
        """Re-render the icon and badge background (theme change)."""
        self.icon_label_color = icon_hex_color
        self.icon_badge.setPixmap(qta.icon(self._icon_name, color=icon_hex_color).pixmap(32, 32))
        self.icon_badge.setStyleSheet(
            f"background-color: {badge_bg}; border-radius: 36px; border: none;"
        )

    def enterEvent(self, event):
        self._shadow.setBlurRadius(self._hover_blur)
        self._shadow.setOffset(0, self._hover_offset)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._shadow.setBlurRadius(self._default_blur)
        self._shadow.setOffset(0, self._default_offset)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._pressed = True
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if (self._pressed and event.button() == Qt.MouseButton.LeftButton
                and self.rect().contains(event.position().toPoint())):
            self.clicked.emit()
        self._pressed = False
        super().mouseReleaseEvent(event)
