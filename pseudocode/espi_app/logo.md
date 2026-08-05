# espi_app/logo.py - The ESPI Logo Widget

## Purpose

Defines `ESPILogo`, a small `QLabel` subclass that shows
`espi_app/logo.svg` (a camera aperture / interference emblem) as a
floating circular badge on the landing page, correctly inverted so it
blends into the background on both light and dark theme.

## Why Not a Plain QSvgWidget

`logo.svg` is a real multi tone grayscale graphic (roughly 900 paths,
shaded from black through many grays to near white), not a simple flat
color line icon, and its very first path is an opaque square filling
the whole canvas edge to edge, not a transparent background around a
circular emblem. A plain `QSvgWidget` just displays whatever is baked
into the file: a hard edged square "sticker", not a floating icon. A
single hue `QGraphicsColorizeEffect` (Qt's usual "recolor a widget"
tool) cannot invert lightness or add transparency either, so it would
not fix either problem.

## How It Actually Renders

### _render_circular_masked(svg_path, render_size)

1. Rasterize the SVG with `QSvgRenderer` (the real Qt SVG framework,
   not hand rolled drawing) into a square image, at `render_size`
   pixels, three times larger than the on screen size
   (`_RENDER_SCALE = 3`) so the logo still looks sharp on a high DPI
   (Retina) display after being scaled back down
2. Clip everything outside an inscribed circle to fully transparent,
   using a `QPainterPath` circle as a clip path before rendering the
   SVG into the image

This turns the square "sticker" into a circular badge with a
transparent surround, letting it float on the page like the rest of the
app's icons.

### ESPILogo.__init__(theme_name, size_px=100, parent=None)

1. Render the masked circle once, at high resolution
2. Keep two versions of it:
   - `_dark_bg_pixmap`: the artwork exactly as authored (a dark
     background behind a bright center pattern), shown on the dark
     theme so its dark background blends into the window
   - `_light_bg_pixmap`: an RGB-inverted copy (light background behind
     a dark center pattern; only color channels are inverted, so the
     circular mask's transparency is untouched), shown on the light
     theme for the same blending reason, in reverse
3. Call `set_theme(theme_name)` to display the correct one immediately

### set_theme(theme_name)

Picks whichever of the two pre-rendered pixmaps matches the given
theme, scales it down to the widget's actual on-screen size with smooth
transformation, and sets it as this label's pixmap. Because both
pixmaps were already rendered once at high resolution in `__init__`,
switching themes is just picking which one to show; there is no redraw
math to do again, even though this can happen every time the user
changes the theme.

## Why This Design

- Rendering once, at high resolution, up front, and keeping both
  theme's pixmaps in memory means a live theme switch is instant: no
  re-rasterizing the SVG, just swapping which already-rendered image is
  shown
- Inverting colors instead of maintaining two separate SVG source files
  guarantees the light and dark versions can never visually drift apart
  from each other

## Related Files

- `main_window.py`: creates one `ESPILogo` for the landing page, and
  calls `set_theme()` on it from `refresh_theme_icons()` when the theme
  changes
- `logo.svg`: the actual vector artwork this file renders
