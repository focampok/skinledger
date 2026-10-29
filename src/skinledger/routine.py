"""Fixed AM/PM routine rules from plan §13; generic categories, no brands (P12).

Pure functions: the latest capture's raw scores and the noise bands (already
computed by noise.get_bands) are passed in. Unstable aspects are never chosen.
Items are merged to one per category per slot, ordered by skincare step, and
limited-night treatments carry their schedule. Advice is a slot note, never an
item and never a shopping-list entry.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from skinledger import copy
from skinledger.aspects import ASPECT_LABELS, NUMERIC_ASPECTS

# (item name, shopping category, when). The category matches the P09 product
# categories so the shopping list can drop what an active product already covers.
Rule = tuple[str, str, str]

_BHA = copy.ROUTINE_ITEM_BHA
_AHA = copy.ROUTINE_ITEM_AHA
_RETINOL = copy.ROUTINE_ITEM_RETINOL
_GENTLE = copy.ROUTINE_ITEM_CLEANSER
_MOISTURIZER = copy.ROUTINE_ITEM_MOISTURIZER
_FRAGRANCE_FREE = copy.ROUTINE_ITEM_FRAGRANCE_FREE
_SOOTHING = copy.ROUTINE_ITEM_SOOTHING
_CERAMIDE = copy.ROUTINE_ITEM_CERAMIDE
_GEL = copy.ROUTINE_ITEM_GEL
_SPF = copy.ROUTINE_ITEM_SPF

_OILY = (
    (copy.ROUTINE_ITEM_NIACINAMIDE, "serum", "AM/PM"),
    (_GEL, "moisturizer", "AM/PM"),
)
_SUN = (
    (_SPF, "sunscreen", "AM"),
    (copy.ROUTINE_ITEM_VITAMIN_C, "serum", "AM"),
)
_RETINOL_RULE = (
    (_RETINOL, "retinoid", "PM"),
    (_SPF, "sunscreen", "AM"),
)
_EYE = ((copy.ROUTINE_ITEM_CAFFEINE, "eye cream", "AM"),)

_RULES: dict[str, tuple[Rule, ...]] = {
    "oiliness": _OILY,
    "pore": _OILY,
    "moisture": ((_CERAMIDE, "moisturizer", "AM/PM"),),
    "age_spot": _SUN,
    "radiance": _SUN,
    "redness": (
        (_FRAGRANCE_FREE, "cleanser", "AM/PM"),
        (_SOOTHING, "moisturizer", "AM/PM"),
    ),
    "acne": ((_BHA, "cleanser", "PM"),),
    "texture": ((_AHA, "exfoliant", "PM"),),
    "wrinkle": _RETINOL_RULE,
    "firmness": _RETINOL_RULE,
    "dark_circle_v2": _EYE,
    "eye_bag": _EYE,
    "tear_trough": _EYE,
    "droopy_upper_eyelid": _EYE,
    "droopy_lower_eyelid": _EYE,
}

_ALWAYS_AM = (
    (_GENTLE, "cleanser", "AM"),
    (_MOISTURIZER, "moisturizer", "AM"),
    (_SPF, "sunscreen", "AM"),
)
_ALWAYS_PM = (
    (_GENTLE, "cleanser", "PM"),
    (_MOISTURIZER, "moisturizer", "PM"),
)
_EXFOLIANT_NAMES = (_AHA, _BHA)
_EYE_ASPECTS = (
    "dark_circle_v2",
    "eye_bag",
    "tear_trough",
    "droopy_upper_eyelid",
    "droopy_lower_eyelid",
)

# Skincare step order: cleanser, treatment/serum, eye cream, moisturizer, SPF.
_STEP = {
    "cleanser": 1,
    "serum": 2,
    "retinoid": 2,
    "exfoliant": 2,
    "eye cream": 3,
    "moisturizer": 4,
    "sunscreen": 5,
}
_MOISTURIZER_PRIORITY = (_SOOTHING, _CERAMIDE, _GEL, _MOISTURIZER)
_SUNSCREEN_PRIORITY = (_SPF,)


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
    display: str
    aspect: str | None = None
    aspect_label: str | None = None
    alternatives: list[str] = field(default_factory=list)
    nights: list[str] = field(default_factory=list)


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
    am_notes: list[str]
    pm_notes: list[str]
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
        aspect for aspect in NUMERIC_ASPECTS if _is_unstable(band_map, aspect)
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
            am_notes=[],
            pm_notes=[],
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
                    display=name,
                    aspect=aspect,
                    aspect_label=ASPECT_LABELS[aspect],
                )
            )

    retinol = any(item.name == _RETINOL for item in specific)
    aha = any(item.name == _AHA for item in specific)
    bha = any(item.name == _BHA for item in specific)
    redness = "redness" in lowest_aspects
    retinol_nights = _night_names([0, 2, 4, 6]) if retinol else []
    exfoliant_nights = (
        _night_names([1, 3, 5][: 2 if redness else 3]) if (aha or bha) else []
    )

    always_am = [
        RoutineItem(name, category, when, name) for name, category, when in _ALWAYS_AM
    ]
    always_pm = [
        RoutineItem(name, category, when, name) for name, category, when in _ALWAYS_PM
    ]
    am = _merge_slot(
        [item for item in specific if item.when in ("AM", "AM/PM")] + always_am,
        retinol_nights,
        exfoliant_nights,
    )
    pm = _merge_slot(
        [item for item in specific if item.when in ("PM", "AM/PM")] + always_pm,
        retinol_nights,
        exfoliant_nights,
    )
    am_notes, pm_notes = _advice_notes(lowest_aspects)

    return Routine(
        capture_id=int(capture["id"]) if capture.get("id") is not None else None,
        captured_at=str(capture["captured_at"]) if capture.get("captured_at") else None,
        data_label=str(capture["data_label"]) if capture.get("data_label") else None,
        has_bands=has_bands,
        lowest=lowest,
        am=am,
        pm=pm,
        am_notes=am_notes,
        pm_notes=pm_notes,
        week=_build_week(am, pm, retinol_nights, exfoliant_nights),
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


def _night_names(indices: list[int]) -> list[str]:
    return [copy.ROUTINE_DAYS[index] for index in indices]


def _advice_notes(lowest_aspects: list[str]) -> tuple[list[str], list[str]]:
    """Advice is a note under the slot, never an item and never shopped for."""
    am_notes: list[str] = []
    pm_notes: list[str] = []
    if "redness" in lowest_aspects:
        am_notes.append(copy.ROUTINE_ITEM_AVOID_TONERS)
        pm_notes.append(copy.ROUTINE_ITEM_AVOID_TONERS)
    if any(aspect in _EYE_ASPECTS for aspect in lowest_aspects):
        am_notes.append(copy.ROUTINE_EYE_NOTE)
    return am_notes, pm_notes


def _merge_slot(
    candidates: list[RoutineItem],
    retinol_nights: list[str],
    exfoliant_nights: list[str],
) -> list[RoutineItem]:
    """One merged item per category, then ordered by skincare step."""
    groups: dict[str, list[RoutineItem]] = {}
    order: list[str] = []
    for item in candidates:
        if item.category not in groups:
            groups[item.category] = []
            order.append(item.category)
        groups[item.category].append(item)

    merged = [
        _merge_group(category, groups[category], retinol_nights, exfoliant_nights)
        for category in order
    ]
    merged.sort(key=lambda item: (_STEP.get(item.category, 9), order.index(item.category)))
    return merged


def _merge_group(
    category: str,
    items: list[RoutineItem],
    retinol_nights: list[str],
    exfoliant_nights: list[str],
) -> RoutineItem:
    specific = [item for item in items if item.aspect is not None]
    generic = [item for item in items if item.aspect is None]
    alternatives: list[RoutineItem] = []

    if category == "moisturizer":
        pool = specific or generic
        primary = _pick(pool, _MOISTURIZER_PRIORITY)
        alternatives = _others(pool, primary)
    elif category == "cleanser":
        daily = [item for item in specific if item.name != _BHA]
        if daily:
            primary = daily[0]
        elif generic:
            primary = generic[0]
        else:
            primary = specific[0]
        alternatives = [item for item in specific if item.name != primary.name]
    elif category == "sunscreen":
        pool = specific or generic
        primary = _pick(pool, _SUNSCREEN_PRIORITY)
        alternatives = _others(pool, primary)
    else:
        pool = specific or generic
        primary = pool[0]
        alternatives = _others(pool, primary)

    alt_names = _unique(item.name for item in alternatives)
    variant_nights: dict[str, list[str]] = {}
    for name in alt_names:
        if name == _BHA:
            variant_nights[name] = exfoliant_nights

    nights: list[str] = []
    if primary.name == _RETINOL:
        nights = retinol_nights
    elif primary.name in _EXFOLIANT_NAMES:
        nights = exfoliant_nights

    pieces = [primary.name]
    for name in alt_names:
        if name in variant_nights:
            pieces.append(f"{name} — {', '.join(variant_nights[name])}")
        else:
            pieces.append(name)
    if nights:
        display = f"{primary.name} — {', '.join(nights)}"
    else:
        display = " or ".join(pieces)

    return RoutineItem(
        name=primary.name,
        category=category,
        when=primary.when,
        display=display,
        aspect=primary.aspect,
        aspect_label=primary.aspect_label,
        alternatives=alt_names,
        nights=nights,
    )


def _pick(items: list[RoutineItem], priority: tuple[str, ...]) -> RoutineItem:
    for name in priority:
        for item in items:
            if item.name == name:
                return item
    return items[0]


def _others(items: list[RoutineItem], primary: RoutineItem) -> list[RoutineItem]:
    return [item for item in items if item.name != primary.name]


def _unique(values) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _build_week(
    am: list[RoutineItem],
    pm: list[RoutineItem],
    retinol_nights: list[str],
    exfoliant_nights: list[str],
) -> list[DayPlan]:
    """Keep retinol and AHA/BHA on separate nights; BHA replaces the cleanser."""
    cleanser = next((item for item in pm if item.category == "cleanser"), None)
    bha = _BHA if cleanser is not None and _BHA in cleanser.alternatives else None
    aha = _AHA if any(item.name == _AHA for item in pm) else None
    retinol = _RETINOL if any(item.name == _RETINOL for item in pm) else None
    pm_daily = [item.name for item in pm if not item.nights]

    category_by_name: dict[str, str] = {}
    for item in pm:
        category_by_name[item.name] = item.category
    if bha:
        category_by_name[bha] = "cleanser"
    if aha:
        category_by_name[aha] = "exfoliant"
    if retinol:
        category_by_name[retinol] = "retinoid"

    week: list[DayPlan] = []
    for day in copy.ROUTINE_DAYS:
        nightly = list(pm_daily)
        if day in retinol_nights and retinol:
            nightly.append(retinol)
        if day in exfoliant_nights:
            if bha and cleanser is not None:
                nightly = [
                    bha if name == cleanser.name else name for name in nightly
                ]
            if aha:
                nightly.append(aha)
        nightly.sort(key=lambda name: _STEP.get(category_by_name.get(name, ""), 9))
        week.append(
            DayPlan(day=day, am=[item.name for item in am], pm=nightly)
        )
    return week
