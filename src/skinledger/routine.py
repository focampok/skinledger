"""Fixed AM/PM routine rules from plan §13; generic categories, no brands (P12).

Pure functions: the latest capture's raw scores and the noise bands (already
computed by noise.get_bands) are passed in. Unstable aspects are never chosen.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from skinledger import copy
from skinledger.aspects import ASPECT_LABELS, NUMERIC_ASPECTS

# (item name, shopping category, when). The category matches the P09 product
# categories so the shopping list can drop what an active product already covers.
Rule = tuple[str, str, str]

_OILY = (
    (copy.ROUTINE_ITEM_NIACINAMIDE, "serum", "AM/PM"),
    (copy.ROUTINE_ITEM_GEL, "moisturizer", "AM/PM"),
)
_SUN = (
    (copy.ROUTINE_ITEM_SPF, "sunscreen", "AM"),
    (copy.ROUTINE_ITEM_VITAMIN_C, "serum", "AM"),
)
_RETINOL = (
    (copy.ROUTINE_ITEM_RETINOL, "retinoid", "PM"),
    (copy.ROUTINE_ITEM_SPF, "sunscreen", "AM"),
)
_EYE = ((copy.ROUTINE_ITEM_CAFFEINE, "eye cream", "AM"),)

_RULES: dict[str, tuple[Rule, ...]] = {
    "oiliness": _OILY,
    "pore": _OILY,
    "moisture": ((copy.ROUTINE_ITEM_CERAMIDE, "moisturizer", "AM/PM"),),
    "age_spot": _SUN,
    "radiance": _SUN,
    "redness": (
        (copy.ROUTINE_ITEM_FRAGRANCE_FREE, "cleanser", "AM/PM"),
        (copy.ROUTINE_ITEM_SOOTHING, "moisturizer", "AM/PM"),
        (copy.ROUTINE_ITEM_AVOID_TONERS, "", "AM/PM"),
    ),
    "acne": ((copy.ROUTINE_ITEM_BHA, "cleanser", "PM"),),
    "texture": ((copy.ROUTINE_ITEM_AHA, "exfoliant", "PM"),),
    "wrinkle": _RETINOL,
    "firmness": _RETINOL,
    "dark_circle_v2": _EYE,
    "eye_bag": _EYE,
    "tear_trough": _EYE,
    "droopy_upper_eyelid": _EYE,
    "droopy_lower_eyelid": _EYE,
}

_ALWAYS_AM = (
    (copy.ROUTINE_ITEM_CLEANSER, "cleanser", "AM"),
    (copy.ROUTINE_ITEM_MOISTURIZER, "moisturizer", "AM"),
    (copy.ROUTINE_ITEM_SPF, "sunscreen", "AM"),
)
_ALWAYS_PM = (
    (copy.ROUTINE_ITEM_CLEANSER, "cleanser", "PM"),
    (copy.ROUTINE_ITEM_MOISTURIZER, "moisturizer", "PM"),
)
_RETINOL_NAME = copy.ROUTINE_ITEM_RETINOL
_EXFOLIANT_NAMES = (copy.ROUTINE_ITEM_AHA, copy.ROUTINE_ITEM_BHA)


@dataclass(slots=True)
class LowAspect:
    aspect: str
    label: str
    score: float
    band: float | None


@dataclass(slots=True)
class RoutineItem:
    name: str
    category: str
    when: str
    aspect: str | None = None
    aspect_label: str | None = None


@dataclass(slots=True)
class DayPlan:
    day: str
    am: list[str]
    pm: list[str]


@dataclass(slots=True)
class Routine:
    capture_id: int | None
    captured_at: str | None
    data_label: str | None
    has_bands: bool
    lowest: list[LowAspect]
    am: list[RoutineItem]
    pm: list[RoutineItem]
    week: list[DayPlan]
    notes: list[str]
    acne_lowest: bool
    unstable_excluded: bool


def build_routine(
    capture: Mapping[str, object] | None,
    bands: Mapping[str, Mapping[str, object]] | None,
) -> Routine:
    """Build the routine from the latest successful capture and the stored bands."""
    band_map = bands if isinstance(bands, Mapping) else {}
    has_bands = bool(band_map)
    unstable = [
        aspect
        for aspect in NUMERIC_ASPECTS
        if _is_unstable(band_map, aspect)
    ]

    if capture is None:
        return Routine(
            capture_id=None,
            captured_at=None,
            data_label=None,
            has_bands=has_bands,
            lowest=[],
            am=[],
            pm=[],
            week=[],
            notes=[copy.ROUTINE_NO_CAPTURE],
            acne_lowest=False,
            unstable_excluded=bool(unstable),
        )

    scores = _scores(capture)
    notes: list[str] = []
    if has_bands:
        eligible = [
            aspect
            for aspect in NUMERIC_ASPECTS
            if aspect in scores and not _is_unstable(band_map, aspect)
        ]
        if len(eligible) < 3:
            notes.append(copy.ROUTINE_FEW_STABLE)
        if not eligible:
            notes.append(copy.ROUTINE_ALL_UNSTABLE)
        if unstable:
            notes.append(copy.ROUTINE_UNSTABLE_EXCLUDED)
    else:
        eligible = [aspect for aspect in NUMERIC_ASPECTS if aspect in scores]
        notes.append(copy.ROUTINE_ONE_CAPTURE)

    ordered = sorted(
        eligible, key=lambda aspect: (scores[aspect], NUMERIC_ASPECTS.index(aspect))
    )
    lowest_aspects = ordered[:3]
    lowest = [
        LowAspect(
            aspect=aspect,
            label=ASPECT_LABELS[aspect],
            score=float(scores[aspect]),
            band=_band(band_map, aspect),
        )
        for aspect in lowest_aspects
    ]

    specific: list[RoutineItem] = []
    for aspect in lowest_aspects:
        for name, category, when in _RULES.get(aspect, ()):
            specific.append(
                RoutineItem(
                    name=name,
                    category=category,
                    when=when,
                    aspect=aspect,
                    aspect_label=ASPECT_LABELS[aspect],
                )
            )

    always_am = [RoutineItem(name, category, when) for name, category, when in _ALWAYS_AM]
    always_pm = [RoutineItem(name, category, when) for name, category, when in _ALWAYS_PM]
    am = _dedupe(
        [item for item in specific if item.when in ("AM", "AM/PM")] + always_am
    )
    pm = _dedupe(
        [item for item in specific if item.when in ("PM", "AM/PM")] + always_pm
    )

    return Routine(
        capture_id=int(capture["id"]) if capture.get("id") is not None else None,
        captured_at=str(capture["captured_at"]) if capture.get("captured_at") else None,
        data_label=str(capture["data_label"]) if capture.get("data_label") else None,
        has_bands=has_bands,
        lowest=lowest,
        am=am,
        pm=pm,
        week=_build_week(am, pm, lowest_aspects),
        notes=notes,
        acne_lowest=bool(lowest_aspects) and lowest_aspects[0] == "acne",
        unstable_excluded=bool(unstable),
    )


def _scores(capture: Mapping[str, object]) -> dict[str, float]:
    raw = capture.get("scores") or {}
    if not isinstance(raw, Mapping):
        return {}
    scores: dict[str, float] = {}
    for aspect in NUMERIC_ASPECTS:
        value = raw.get(aspect)
        if value is None:
            continue
        try:
            scores[aspect] = float(value)
        except (TypeError, ValueError):
            continue
    return scores


def _is_unstable(bands: Mapping[str, Mapping[str, object]], aspect: str) -> bool:
    entry = bands.get(aspect)
    return bool(entry is not None and entry.get("unstable"))


def _band(bands: Mapping[str, Mapping[str, object]], aspect: str) -> float | None:
    entry = bands.get(aspect)
    if entry is None or entry.get("band") is None:
        return None
    return float(entry["band"])


def _dedupe(items: list[RoutineItem]) -> list[RoutineItem]:
    seen: set[str] = set()
    result: list[RoutineItem] = []
    for item in items:
        if item.name in seen:
            continue
        seen.add(item.name)
        result.append(item)
    return result


def _build_week(
    am: list[RoutineItem], pm: list[RoutineItem], lowest_aspects: list[str]
) -> list[DayPlan]:
    """Alternate retinol and AHA/BHA nights; redness caps exfoliating at 2 nights."""
    pm_names = [item.name for item in pm]
    retinol = _RETINOL_NAME in pm_names
    exfoliants = [name for name in _EXFOLIANT_NAMES if name in pm_names]
    redness = "redness" in lowest_aspects
    active = {_RETINOL_NAME, *exfoliants}
    pm_base = [name for name in pm_names if name not in active]

    retinol_nights = {0, 2, 4, 6} if retinol else set()
    exfoliant_nights: set[int] = set()
    if exfoliants:
        count = 2 if redness else 3
        exfoliant_nights = set([1, 3, 5][:count]) - retinol_nights

    week: list[DayPlan] = []
    for index, day in enumerate(copy.ROUTINE_DAYS):
        nightly = list(pm_base)
        if index in retinol_nights:
            nightly.append(_RETINOL_NAME)
        if index in exfoliant_nights:
            nightly.extend(exfoliants)
        week.append(DayPlan(day=day, am=[item.name for item in am], pm=nightly))
    return week
