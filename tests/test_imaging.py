"""P03 imaging tests: in-memory validation, EXIF strip and "no file ever written"."""

import io
import tempfile

import pytest
import respx
from PIL import Image

from skinledger.imaging import MAX_IMAGE_BYTES, ImageRejected, prepare


def jpeg_bytes(size=(800, 1000), color=(180, 140, 120), exif=None) -> bytes:
    buffer = io.BytesIO()
    image = Image.new("RGB", size, color)
    if exif is None:
        image.save(buffer, format="JPEG")
    else:
        image.save(buffer, format="JPEG", exif=exif)
    return buffer.getvalue()


def png_bytes(size=(800, 800)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGBA", size, (255, 0, 0, 128)).save(buffer, format="PNG")
    return buffer.getvalue()


def gif_bytes(size=(800, 800)) -> bytes:
    buffer = io.BytesIO()
    Image.new("P", size).save(buffer, format="GIF")
    return buffer.getvalue()


def test_prepare_accepts_jpeg_and_reports_dimensions():
    prepared = prepare(jpeg_bytes(size=(800, 1000)))

    assert prepared.content_type == "image/jpeg"
    assert (prepared.width, prepared.height) == (800, 1000)
    assert prepared.data.startswith(b"\xff\xd8")


def test_prepare_reencodes_png_to_jpeg_in_memory():
    prepared = prepare(png_bytes())

    assert prepared.content_type == "image/jpeg"
    with Image.open(io.BytesIO(prepared.data)) as image:
        assert image.format == "JPEG"
        assert image.mode == "RGB"


def test_small_image_is_rejected_before_any_request():
    with respx.mock as router:
        with pytest.raises(ImageRejected) as excinfo:
            prepare(jpeg_bytes(size=(300, 800)))
        assert excinfo.value.code == "error_below_min_image_size"
        assert len(router.calls) == 0


def test_gif_is_rejected_as_unsupported():
    with pytest.raises(ImageRejected) as excinfo:
        prepare(gif_bytes())

    assert excinfo.value.code == "unsupported_format"


def test_corrupt_bytes_are_rejected_as_unsupported():
    with pytest.raises(ImageRejected) as excinfo:
        prepare(b"this is not an image")

    assert excinfo.value.code == "unsupported_format"


def test_input_over_ten_megabytes_is_rejected_early():
    with pytest.raises(ImageRejected) as excinfo:
        prepare(b"\x00" * (MAX_IMAGE_BYTES + 1))

    assert excinfo.value.code == "error_exceed_max_image_size"


def test_exif_metadata_is_stripped_from_the_output():
    exif = Image.Exif()
    exif[0x010F] = "UnitTestCamera"
    exif[0x0110] = "UnitTestModel"
    gps = exif.get_ifd(0x8825)
    gps[1] = "N"
    gps[2] = (14.0, 36.0, 0.0)
    source = jpeg_bytes(exif=exif)
    assert Image.open(io.BytesIO(source)).getexif()

    prepared = prepare(source)

    with Image.open(io.BytesIO(prepared.data)) as image:
        assert len(image.getexif()) == 0
        assert "exif" not in image.info


def test_exif_orientation_is_applied_to_dimensions():
    exif = Image.Exif()
    exif[0x0112] = 6
    prepared = prepare(jpeg_bytes(size=(800, 1000), exif=exif))

    assert (prepared.width, prepared.height) == (1000, 800)


def test_prepare_creates_no_file(tmp_path, monkeypatch):
    cwd = tmp_path / "cwd"
    temp_dir = tmp_path / "temp"
    cwd.mkdir()
    temp_dir.mkdir()
    monkeypatch.chdir(cwd)
    monkeypatch.setattr(tempfile, "tempdir", str(temp_dir))

    prepare(jpeg_bytes())

    assert list(cwd.iterdir()) == []
    assert list(temp_dir.iterdir()) == []
