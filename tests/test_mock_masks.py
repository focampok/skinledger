"""P05b acceptance tests: mock masks look like overlays, not flat grey images."""

from __future__ import annotations

import io

from PIL import Image

from skinledger import mock_masks
from skinledger.aspects import SD_ACTIONS

SKIN_TYPE_REGIONS = ("whole", "t_zone", "u_zone")
ASPECTS = tuple(SD_ACTIONS) + tuple(f"skin_type_{region}" for region in SKIN_TYPE_REGIONS)


def _mask(aspect: str):
    data = mock_masks.mock_mask_png(aspect)
    assert isinstance(data, bytes)
    return Image.open(io.BytesIO(data))


def test_mock_mask_is_a_full_size_transparent_rgba_png():
    with _mask("acne") as image:
        assert image.format == "PNG"
        assert image.mode == "RGBA"
        assert image.size == (mock_masks.MASK_WIDTH, mock_masks.MASK_HEIGHT)
        alpha = image.getchannel("A")
        assert alpha.getpixel((0, 0)) == 0
        assert alpha.getpixel((mock_masks.MASK_WIDTH - 1, 0)) == 0
        assert alpha.getextrema()[1] <= mock_masks.MAX_ALPHA
        assert alpha.getextrema()[1] > 0


def test_mock_mask_has_one_visible_soft_region_that_does_not_hide_the_photo():
    with _mask("acne") as image:
        alpha = image.getchannel("A")
        bbox = alpha.getbbox()
        assert bbox is not None
        centre = ((bbox[0] + bbox[2]) // 2, (bbox[1] + bbox[3]) // 2)
        red, green, blue, opacity = image.getpixel(centre)
        assert opacity > 0
        assert (red, green, blue) != (255, 255, 255)
        # Semi-transparent: the photo underneath stays visible.
        assert opacity < 128


def test_every_aspect_gets_a_distinct_region():
    boxes = {}
    for aspect in ASPECTS:
        with _mask(aspect) as image:
            boxes[aspect] = image.getchannel("A").getbbox()

    assert all(box is not None for box in boxes.values())
    assert len(set(boxes.values())) == len(ASPECTS)
    assert boxes["acne"] != boxes["wrinkle"]
    assert boxes["skin_type_whole"] != boxes["skin_type_t_zone"]


def test_mock_url_parsing_keeps_the_aspect():
    assert mock_masks.aspect_from_mock_url("mock://mask/acne/0.png") == "acne"
    assert (
        mock_masks.aspect_from_mock_url("mock://mask/skin_type_t_zone/0.png")
        == "skin_type_t_zone"
    )
    assert mock_masks.aspect_from_mock_url("https://example.invalid/x.png") == "unknown"


def test_mock_masks_are_cached():
    assert mock_masks.mock_mask_png("acne") is mock_masks.mock_mask_png("acne")
