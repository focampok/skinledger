"""Run ONE real YouCam Skin Analysis (16 units) against a photo passed by path.

Usage:
    uv run python scripts/smoke_real.py ~/selfie.jpg

The photo is read into memory only; it is never copied. Masks go to ./smoke_masks/
(gitignored) so they can be inspected. Refuses to run when YOUCAM_MOCK=true.
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
from io import BytesIO
from pathlib import Path

from PIL import Image

from skinledger.aspects import SD_ACTIONS
from skinledger.config import get_settings
from skinledger.imaging import ImageRejected, prepare
from skinledger.youcam import (
    SKIN_TYPE_REGIONS,
    YouCamClient,
    YouCamConfigError,
    YouCamError,
    YouCamTaskError,
    analysis_slot,
    friendly_message,
)

MASK_DIR = Path("smoke_masks")


async def run(photo_path: Path) -> int:
    settings = get_settings()
    if settings.youcam_mock:
        print("Refusing to run: YOUCAM_MOCK=true. Set YOUCAM_MOCK=false for a real analysis.")
        return 2

    if not photo_path.is_file():
        print(f"Photo not found: {photo_path}")
        return 2

    print(f"This will spend {settings.units_per_analysis} units. Type yes:", end=" ")
    answer = input().strip().lower()
    if answer != "yes":
        print("Cancelled; no units were spent.")
        return 2

    raw = photo_path.read_bytes()
    try:
        image = prepare(raw)
    except ImageRejected as exc:
        print(f"Rejected before any API call: {exc.code}")
        print(friendly_message(exc.code))
        print("Units spent: 0")
        return 1
    finally:
        del raw

    client = YouCamClient(poll_interval=settings.youcam_poll_interval_s)
    try:
        async with analysis_slot():
            file_id = await client.upload_file(image)
            del image
            task_id = await client.create_task(file_id)
            print(f"Task created: {task_id}")
            result = await client.poll(task_id)
    except YouCamConfigError as exc:
        print(f"Configuration error: {exc}")
        return 1
    except YouCamTaskError as exc:
        print(f"Analysis error: {exc.error_code}")
        print(exc.user_message)
        print("Units spent: 0")
        return 1
    except YouCamError as exc:
        print(f"Error: {exc.user_message}")
        return 1

    if result.status == "timeout":
        print(f"Still running after the poll window. Resume task_id={task_id} later.")
        print("Units spent: unknown until the task finishes")
        return 1

    print(f"Status: {result.status}")
    print(f"Units spent: {settings.units_per_analysis}")

    MASK_DIR.mkdir(exist_ok=True)
    raw_path = MASK_DIR / "result_raw.json"
    raw_path.write_text(json.dumps(result.raw, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Raw result: {raw_path.resolve()}")

    print("Aspects:")
    for aspect in SD_ACTIONS:
        if aspect == "skin_type":
            for region in SKIN_TYPE_REGIONS:
                key = f"skin_type_{region}"
                print(f"  {key}: {result.categorical.get(key, '(missing)')}")
        else:
            score = result.scores.get(aspect)
            print(f"  {aspect}: {score if score is not None else '(missing)'}")

    MASK_DIR.mkdir(exist_ok=True)
    downloaded = 0
    for aspect, urls in result.mask_urls.items():
        safe_aspect = re.sub(r"[^A-Za-z0-9_.-]", "_", aspect)
        for index, url in enumerate(urls):
            try:
                data = await client.download(url, task_id=task_id)
            except YouCamError as exc:
                print(f"  mask {aspect}[{index}]: download failed ({exc.user_message})")
                continue
            with Image.open(BytesIO(data)) as mask:
                assert mask.mode != "RGB", (
                    f"{aspect}[{index}] is RGB without alpha; it may embed the photo. "
                    "Set STORE_MASKS=false and tell Francisco."
                )
                print(f"  mask {aspect}[{index}]: {mask.size} {mask.mode}")
            (MASK_DIR / f"{safe_aspect}_{index}.png").write_bytes(data)
            downloaded += 1

    print(f"Masks downloaded: {downloaded}")
    print(f"Inspect them in: {MASK_DIR.resolve()}")
    return 0


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: uv run python scripts/smoke_real.py ~/selfie.jpg")
        return 2
    return asyncio.run(run(Path(sys.argv[1]).expanduser()))


if __name__ == "__main__":
    raise SystemExit(main())
