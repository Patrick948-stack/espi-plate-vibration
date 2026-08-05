"""
generate_icons.py

One time script that turns espi_app/logo.svg into the raster icon files
PyInstaller actually needs. PyInstaller's --icon flag cannot read an SVG
file directly. Windows needs a .ico file, and Mac needs a .icns file, both
of which have to be built from a plain raster image first.

Run once from the project root, with venv_physics active:
    python packaging/generate_icons.py

Reuses espi_app.logo's own _render_circular_masked() function instead of
re-implementing the SVG rendering and circular masking a second time, so
the app icon always matches whatever the on-screen logo actually looks
like.

Writes three files into packaging/assets/:
    logo.png   1024x1024, the base image, also useful on its own
    logo.ico   Windows icon, multiple sizes packed into one file
    logo.icns  Mac icon
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from PyQt6.QtWidgets import QApplication
from PIL import Image

from espi_app.logo import _render_circular_masked, _SVG_PATH

ASSETS_DIR = Path(__file__).resolve().parent / "assets"
RENDER_SIZE = 1024

# Windows .ico files are expected to carry several sizes bundled together,
# so the OS can pick the sharpest one for whatever context it needs
# (taskbar, alt-tab, file explorer thumbnail, and so on).
ICO_SIZES = [(16, 16), (32, 32), (48, 48), (128, 128), (256, 256)]


def main():
    # QSvgRenderer and QImage both need a running QApplication to work,
    # even though nothing actually gets shown on screen here.
    app = QApplication(sys.argv)

    ASSETS_DIR.mkdir(exist_ok=True)

    print(f"Rendering {_SVG_PATH.name} at {RENDER_SIZE}x{RENDER_SIZE}...")
    qimage = _render_circular_masked(_SVG_PATH, RENDER_SIZE)

    png_path = ASSETS_DIR / "logo.png"
    qimage.save(str(png_path), "PNG")
    print(f"Wrote {png_path}")

    # Hand off to Pillow for the .ico and .icns formats, since Qt itself
    # has no built in writer for either one.
    pil_image = Image.open(png_path).convert("RGBA")

    ico_path = ASSETS_DIR / "logo.ico"
    pil_image.save(ico_path, format="ICO", sizes=ICO_SIZES)
    print(f"Wrote {ico_path}")

    icns_path = ASSETS_DIR / "logo.icns"
    pil_image.save(icns_path, format="ICNS")
    print(f"Wrote {icns_path}")


if __name__ == "__main__":
    main()
