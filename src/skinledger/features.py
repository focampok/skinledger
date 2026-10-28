"""One place to enable pages that are built in later steps (P08, P09, P12)."""

from __future__ import annotations

FEATURES: dict[str, bool] = {
    "timeline": False,
    "products": False,
    "routine": False,
}


def is_enabled(name: str) -> bool:
    return FEATURES.get(name, False)
