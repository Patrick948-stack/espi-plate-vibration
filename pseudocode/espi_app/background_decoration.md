# espi_app/background_decoration.py - Corner Dot Background Decoration

## Purpose

Paints a subtle, purely decorative dot pattern in the top-left and
top-right corners of the landing page background, using QPainter
directly instead of an image file, so it stays crisp at any resolution
and can recolor itself instantly on a theme change.

## The CornerDotDecoration Class

A plain Python class, not a widget. It computes the dot positions for
one corner once and holds the current color; `LandingBackground` (below)
is what actually calls it from a real `paintEvent`.

### _build_corner_cluster()

Builds the dot centers for one corner, anchored to that corner's own
(0, 0):

1. Loop over 6 rows (`_ROWS = 6`)
2. Row 0 (the top row) gets 6 dots; each row below gets one fewer
   (row 1 gets 5, row 2 gets 4, and so on down to row 5's single dot)
3. Every dot in a row is spaced `_SPACING` (15px) apart, starting
   `_MARGIN` (28px) from the corner
4. Return the full list: 6 + 5 + 4 + 3 + 2 + 1 = 21 points

This is what makes the cluster read as an inverted triangle (wide at the
top, narrowing as it goes down and toward the window's center) instead
of a plain rectangular grid of dots.

### set_theme(theme_name, color_hex)

Rebuilds the dot color from the given hex string, then sets its opacity:
0.10 (10%) for light mode, 0.12 (12%) for dark mode, both intentionally
subtle. Does not trigger a repaint by itself.

### paint(painter, widget_width)

1. Turn on antialiasing so small circles look smooth, not jagged
2. Draw the top-left cluster exactly as computed
3. Draw the top-right cluster: the same 21 points, but with each point's
   x mirrored (`widget_width - x`), so it is a perfect mirror image of
   the left cluster, not a second independent computation

Since the point list is built once in `__init__` and reused every call,
`paint()` itself does no allocation beyond the one subtraction per dot
needed for the mirrored side.

## The LandingBackground Class

A `QWidget` subclass used as the landing page's central widget, in place
of a plain `QWidget()`.

### Why This Widget Exists

A `QMainWindow`'s own `paintEvent` cannot be used for this: its central
widget is a child that paints on top of it, and a plain child `QWidget`
does not paint its stylesheet's `background-color` at all unless
`Qt.WidgetAttribute.WA_StyledBackground` is set (the same gotcha
`mode_card.py` hit). `LandingBackground` sets that attribute itself, so
its `paintEvent`:

1. Calls `super().paintEvent(event)` first, which paints the normal
   shared-theme background from the stylesheet
2. Then paints the dot decoration on top of that background

Every other widget on the landing page (logo, title, mode cards,
buttons) is a child added to this widget's layout afterward, and Qt
always paints a widget's own `paintEvent` before its children's, so the
dots end up strictly in the background layer without any layout changes
being needed at all.

### set_theme(theme_name, color_hex)

Called by `LandingPage.refresh_theme_icons()` on every theme change,
alongside the icon/logo/card recoloring it already did. Updates the
decoration's color and calls `self.update()` to trigger a repaint.

## Why This Design

- Painted with QPainter instead of an image asset, so there is nothing
  to swap per theme or per display resolution; only the color changes
- The dot cluster is computed once and reused for both the left cluster
  and (mirrored) the right one, and again across every repaint, keeping
  `paintEvent` itself cheap
- Kept in its own file/class instead of inline in `LandingPage`, so the
  drawing logic is testable on its own and does not bloat the main
  window class

## Related Files

- `main_window.py`: builds `LandingBackground` as `LandingPage`'s
  central widget, and calls `set_theme()` on it from
  `refresh_theme_icons()`
- `styles.py`: supplies `icon_color()`, the same primary-text-color hex
  string this decoration is colored from
- `mode_card.py`: the other widget in this app that needed
  `WA_StyledBackground` for the same reason
