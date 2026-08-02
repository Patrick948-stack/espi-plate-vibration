# espi_app/mode_card.py - The Clickable Mode Selection Card

## Purpose

Defines `ModeCard`, the custom widget behind the two big "Monitor Mode"
and "Scan Mode" buttons on the landing page: an icon in a circular
badge, a bold title, a small divider mark, and a two line description,
styled as a raised card that grows a drop shadow on hover.

## Why Not a Plain QPushButton

A `QPushButton` can only show one label. Each mode card needs an icon,
a title, and a separate description line below it, so `ModeCard` is a
plain `QWidget` instead, with its own `clicked` signal and its own
mouse press/release tracking to behave like a button.

## The ModeCard Class

### __init__(icon_name, title_text, description_text, icon_hex_color, badge_bg, divider_color, parent=None)

1. Set the object name to "ModeCard" (used by `main_window.py`'s
   stylesheet to target this widget specifically)
2. Turn on `WA_StyledBackground`, without it a plain QWidget ignores
   background-color and border from its stylesheet entirely (only
   QFrame and a few others honor those properties by default)
3. Set the mouse cursor to a pointing hand, and a minimum size of
   240x240
4. Build a vertical, centered layout:
   - A circular icon badge (a QLabel styled as a circle, holding a
     qtawesome icon pixmap)
   - The bold title
   - A small horizontal divider line
   - The word-wrapped description
5. Call `set_colors()` to render the icon and badge background for the
   colors passed in
6. Attach a `QGraphicsDropShadowEffect`, starting at a smaller blur
   radius and offset (the "resting" shadow)

### set_colors(icon_hex_color, badge_bg)

Re-renders the icon (as a 32x32 pixmap in the given color) and the
badge's circular background. Called at construction, and again by
`main_window.py`'s `refresh_theme_icons()` whenever the theme changes.

### enterEvent(event) / leaveEvent(event)

On mouse enter, increases the drop shadow's blur radius and vertical
offset, making the card appear to lift up. On mouse leave, sets both
back to their resting values. This is the entire hover effect: no
color change, just the shadow.

### mousePressEvent(event) / mouseReleaseEvent(event)

Mirrors `QPushButton`'s own click semantics by hand: on a left button
press inside the widget, remember that the mouse is down
(`self._pressed = True`). On a left button release, if the mouse was
pressed on this widget and the release point is still inside its
bounds, emit the `clicked` signal. Either way, clear `self._pressed`.
Moving the mouse off the card before releasing (a "changed my mind"
gesture) does not fire a click, matching how a real button behaves.

Because this is a plain `QWidget`, calling `setEnabled(False)` on it
(done by `main_window.py` while a dashboard window is opening) stops it
from receiving mouse events at all, automatically, with no extra guard
code needed in this file.

## Why This Design

- One custom widget instead of a QPushButton plus separate label
  widgets laid on top of it keeps the click handling, the hover shadow,
  and the layout all in one place
- Colors are passed in from outside (`main_window.py`, via
  `styles.py`'s `landing_accent_colors()`) rather than hardcoded here,
  so the same widget works for both light and dark theme without any
  theme-specific logic inside this file

## Related Files

- `main_window.py`: creates the two `ModeCard` instances (Monitor Mode,
  Scan Mode), connects their `clicked` signals, and re-colors them on a
  theme change via `set_colors()`
- `styles.py`: supplies `landing_accent_colors()`, the color tokens this
  widget is rendered with
