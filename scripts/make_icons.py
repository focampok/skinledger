"""Generate the PWA icons: flat colour with the letters "SL", no faces.

Run with: uv run python scripts/make_icons.py
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT_DIR = Path(__file__).resolve().parents[1] / "src/skinledger/web/static/icons"
BACKGROUND = (31, 111, 92)
FOREGROUND = (255, 255, 255)
SIZES = (192, 512)
TEXT = "SL"


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf", size)
    except OSError:
        return ImageFont.load_default(size)


def make_icon(size: int) -> Image.Image:
    """Draw one square icon with centred letters."""
    image = Image.new("RGB", (size, size), BACKGROUND)
    draw = ImageDraw.Draw(image)
    font = _font(int(size * 0.42))
    left, top, right, bottom = draw.textbbox((0, 0), TEXT, font=font)
    position = (
        (size - (right - left)) / 2 - left,
        (size - (bottom - top)) / 2 - top,
    )
    draw.text(position, TEXT, font=font, fill=FOREGROUND)
    return image


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for size in SIZES:
        path = OUT_DIR / f"icon-{size}.png"
        make_icon(size).save(path, format="PNG")
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
