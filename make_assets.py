"""Generate PNG image assets for the eon_meter custom component.

Creates (HA 2026.3+ brands spec compliant):
  custom_components/eon_meter/icon.png      — 256×256 app icon (red rounded square, white bold "E")
  custom_components/eon_meter/icon@2x.png   — 512×512 retina icon
  custom_components/eon_meter/logo.png      — 400×160 banner, TRANSPARENT background
  custom_components/eon_meter/logo@2x.png   — 800×320 hDPI banner, TRANSPARENT background

HA spec requirements:
  icon.png    : 256×256 px, square
  icon@2x.png : 512×512 px, square
  logo.png    : shortest side 128–256 px, transparent preferred
  logo@2x.png : shortest side 256–512 px, transparent preferred

Run with:  python make_assets.py
Requires:  Pillow (pip install Pillow)
"""

import os
from PIL import Image, ImageDraw, ImageFont

OUT_DIR = os.path.join(os.path.dirname(__file__), "custom_components", "eon_meter")

RED     = (204, 0, 0, 255)
WHITE   = (255, 255, 255, 255)
DARK    = (34, 34, 34, 255)
TRANSP  = (0, 0, 0, 0)

FONT_PATHS = [
    "C:/Windows/Fonts/arialbd.ttf",   # Windows bold
    "C:/Windows/Fonts/ariblk.ttf",    # Arial Black
    "C:/Windows/Fonts/arial.ttf",     # Arial regular
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # Linux fallback
    "/System/Library/Fonts/Helvetica.ttc",                   # macOS fallback
]


def _get_font(size: int) -> ImageFont.ImageFont:
    for path in FONT_PATHS:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _center_text(draw: ImageDraw.ImageDraw, text: str, font, canvas_w: int, canvas_h: int,
                 x_offset=0, y_offset=0):
    """Return (x, y) to draw text centered in a canvas, with optional offsets."""
    bb = draw.textbbox((0, 0), text, font=font)
    tw = bb[2] - bb[0]
    th = bb[3] - bb[1]
    x = (canvas_w - tw) // 2 - bb[0] + x_offset
    y = (canvas_h - th) // 2 - bb[1] + y_offset
    return x, y


def make_icon(size: int, radius: int, font_size: int) -> Image.Image:
    """Square icon: red rounded rectangle with centred white 'E'."""
    img = Image.new("RGBA", (size, size), TRANSP)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=RED)
    font = _get_font(font_size)
    x, y = _center_text(d, "E", font, size, size)
    d.text((x, y), "E", font=font, fill=WHITE)
    return img


def make_logo(width: int = 400, height: int = 160) -> Image.Image:
    """Horizontal banner: red rounded square icon + 'E.ON Meter' label.

    Background is TRANSPARENT so it works in both HA light and dark themes.
    """
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))   # transparent!
    d = ImageDraw.Draw(img)

    # Scale factor relative to the 400×160 reference size
    scale = width / 400

    # --- Icon square ---
    sq   = int(120 * scale)
    pad  = int(20 * scale)
    top  = (height - sq) // 2            # vertically centred
    d.rounded_rectangle([pad, top, pad + sq, top + sq], radius=int(22 * scale), fill=RED)

    # 'E' inside the icon square
    fe = _get_font(int(86 * scale))
    ex, ey = _center_text(d, "E", fe, sq, sq, x_offset=pad, y_offset=top)
    d.text((ex, ey), "E", font=fe, fill=WHITE)

    # --- Text 'E.ON Meter' to the right of the icon ---
    text_x = pad + sq + int(22 * scale)
    ft = _get_font(int(44 * scale))
    bb = d.textbbox((0, 0), "E.ON Meter", font=ft)
    th = bb[3] - bb[1]
    ty = (height - th) // 2 - bb[1]
    d.text((text_x, ty), "E.ON Meter", font=ft, fill=DARK)

    return img


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)

    icon_256 = make_icon(256, 48, 178)
    icon_256.save(os.path.join(OUT_DIR, "icon.png"))
    print("✅  icon.png        256×256")

    icon_512 = make_icon(512, 96, 356)
    icon_512.save(os.path.join(OUT_DIR, "icon@2x.png"))
    print("✅  icon@2x.png     512×512")

    logo = make_logo(400, 160)
    logo.save(os.path.join(OUT_DIR, "logo.png"))
    print("✅  logo.png        400×160  (transparent background)")

    logo_2x = make_logo(800, 320)
    logo_2x.save(os.path.join(OUT_DIR, "logo@2x.png"))
    print("✅  logo@2x.png     800×320  (transparent background)")

    print("\nAll assets written to:", OUT_DIR)
