"""In-memory image validation and EXIF strip; never writes image bytes to disk."""

from __future__ import annotations

import io
from dataclasses import dataclass

import pillow_heif
from PIL import Image, ImageOps

# iPhone sends HEIC when Camera > Formats is set to High Efficiency. pillow-heif
# ships libheif in its wheel, so no system package is needed. Decoding still
# happens in memory; the original bytes are never written and are dropped once
# the JPEG re-encode below is done.
pillow_heif.register_heif_opener()

MAX_IMAGE_BYTES = 10 * 1024 * 1024
MIN_SHORT_SIDE = 480
JPEG_QUALITY = 92
JPEG_FALLBACK_QUALITY = 85
MAX_IMAGE_PIXELS = 40_000_000

# Pillow refuses to decode images above this pixel count (approx. 40 MP).
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS

# HEIF/HEIC is decoded by pillow-heif and re-encoded to JPEG like every other input.
ACCEPTED_FORMATS = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "HEIF": "image/heif",
    "HEIC": "image/heic",
}


@dataclass(frozen=True, slots=True)
class PreparedImage:
    """Validated, EXIF-free JPEG bytes ready to send to YouCam (in memory only)."""

    data: bytes
    content_type: str
    width: int
    height: int


class ImageRejected(Exception):
    """Raised before any API call when a photo cannot be used."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def prepare(data: bytes) -> PreparedImage:
    """Validate, orient and re-encode an image entirely in memory.

    The returned JPEG has no EXIF, no ICC profile and no other metadata. This
    function never writes the input or the output to a path.
    """
    if len(data) > MAX_IMAGE_BYTES:
        raise ImageRejected("error_exceed_max_image_size")

    try:
        with Image.open(io.BytesIO(data)) as opened:
            opened.load()
            if opened.format not in ACCEPTED_FORMATS:
                raise ImageRejected("unsupported_format")
            image = ImageOps.exif_transpose(opened)
            image.load()
    except ImageRejected:
        raise
    except Image.DecompressionBombError:
        raise ImageRejected("unsupported_format") from None
    except (OSError, ValueError):
        raise ImageRejected("unsupported_format") from None

    width, height = image.size
    if min(width, height) < MIN_SHORT_SIDE:
        raise ImageRejected("error_below_min_image_size")

    if image.mode in ("RGBA", "LA") or (
        image.mode == "P" and "transparency" in image.info
    ):
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.getchannel("A"))
        image = background
    elif image.mode != "RGB":
        image = image.convert("RGB")

    for key in ("exif", "icc_profile", "XML:com.adobe.xmp"):
        image.info.pop(key, None)

    for quality in (JPEG_QUALITY, JPEG_FALLBACK_QUALITY):
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=quality)
        encoded = buffer.getvalue()
        if len(encoded) <= MAX_IMAGE_BYTES:
            return PreparedImage(
                data=encoded,
                content_type="image/jpeg",
                width=width,
                height=height,
            )

    raise ImageRejected("error_exceed_max_image_size")
