"""Mock-mode masks: transparent RGBA PNGs with one soft coloured region per aspect.

A mock mask must behave like a real overlay: full document size, transparent outside
the region, and semi-transparent inside it so the photo underneath stays visible.
"""

from __future__ import annotations

import io
import re
from functools import cache

from PIL import Image

MASK_WIDTH = 1920
MASK_HEIGHT = 2560
MAX_ALPHA = 110
_PREVIEW_SIZE = (160, 213)

_MASK_URL_RE = re.compile(r"mock://mask/([^/]+)/")

# aspect -> (centre x, centre y, radius x, radius y, colour) as fractions of the mask.
_REGIONS: dict[str, tuple[float, float, float, float, tuple[int, int, int]]] = {
    "wrinkle": (0.50, 0.17, 0.34, 0.08, (214, 118, 72)),
    "droopy_upper_eyelid": (0.38, 0.34, 0.14, 0.05, (150, 120, 210)),
    "droopy_lower_eyelid": (0.62, 0.40, 0.14, 0.05, (140, 130, 200)),
    "firmness": (0.32, 0.53, 0.16, 0.12, (80, 150, 200)),
    "acne": (0.50, 0.70, 0.18, 0.10, (210, 80, 90)),
    "moisture": (0.50, 0.45, 0.36, 0.30, (70, 165, 175)),
    "eye_bag": (0.39, 0.42, 0.13, 0.04, (120, 110, 190)),
    "dark_circle_v2": (0.61, 0.45, 0.13, 0.045, (100, 100, 180)),
    "age_spot": (0.70, 0.50, 0.12, 0.08, (190, 130, 70)),
    "radiance": (0.50, 0.40, 0.08, 0.16, (225, 190, 80)),
    "redness": (0.34, 0.58, 0.14, 0.10, (220, 90, 90)),
    "oiliness": (0.50, 0.55, 0.09, 0.07, (200, 170, 70)),
    "pore": (0.57, 0.55, 0.07, 0.06, (170, 140, 90)),
    "texture": (0.66, 0.58, 0.14, 0.12, (130, 170, 120)),
    "tear_trough": (0.40, 0.47, 0.10, 0.035, (110, 120, 200)),
    "skin_type_whole": (0.50, 0.48, 0.34, 0.32, (90, 170, 140)),
    "skin_type_t_zone": (0.50, 0.35, 0.16, 0.22, (90, 150, 200)),
    "skin_type_u_zone": (0.50, 0.60, 0.28, 0.16, (170, 140, 210)),
}

_DEFAULT_REGION = (0.50, 0.50, 0.22, 0.16, (120, 160, 210))


def aspect_from_mock_url(url: str) -> str:
    """Extract the aspect from a mock URL such as mock://mask/acne/0.png."""
    match = _MASK_URL_RE.match(url)
    return match.group(1) if match else "unknown"


def _alpha(region: tuple[float, float, float, float, tuple[int, int, int]]) -> Image.Image:
    centre_x, centre_y, radius_x, radius_y, _colour = region
    small = Image.new("L", _PREVIEW_SIZE, 0)
    pixels = small.load()
    scaled_x = centre_x * _PREVIEW_SIZE[0]
    scaled_y = centre_y * _PREVIEW_SIZE[1]
    scaled_rx = max(radius_x * _PREVIEW_SIZE[0], 1.0)
    scaled_ry = max(radius_y * _PREVIEW_SIZE[1], 1.0)
    for y in range(_PREVIEW_SIZE[1]):
        for x in range(_PREVIEW_SIZE[0]):
            distance = ((x - scaled_x) / scaled_rx) ** 2 + ((y - scaled_y) / scaled_ry) ** 2
            if distance < 1.0:
                pixels[x, y] = int(MAX_ALPHA * (1.0 - distance) ** 1.5)
    return small.resize((MASK_WIDTH, MASK_HEIGHT), Image.Resampling.BILINEAR)


@cache
def mock_mask_png(aspect: str) -> bytes:
    """Return a cached transparent RGBA PNG with a soft region for this aspect."""
    region = _REGIONS.get(aspect, _DEFAULT_REGION)
    red, green, blue = region[4]
    image = Image.new("RGBA", (MASK_WIDTH, MASK_HEIGHT), (red, green, blue, 0))
    image.putalpha(_alpha(region))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", compress_level=1)
    return buffer.getvalue()


def mock_mask_png_for_url(url: str) -> bytes:
    return mock_mask_png(aspect_from_mock_url(url))
