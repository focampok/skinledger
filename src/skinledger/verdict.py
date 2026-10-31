"""Frozen verdict engine (plan §12): Keep / No measurable change / Worse / Too early.

Pure functions only: this module imports nothing from web/ or the database, does no
I/O, and never reads a secret. Bands are passed in from noise.get_bands; their
``unstable`` flag is read as-is, so NOISE_FLOOR and UNSTABLE_BAND are never redefined
or recomputed here.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from skinledger.aspects import ASPECT_LABELS, NUMERIC_ASPECTS

KEEP = "keep"
NO_CHANGE = "no_change"
WORSE = "worse"
TOO_EARLY = "too_early"
NO_BAND = "no_band"
NEED_CHECKIN = "need_checkin"

KEEP_MESSAGE = "The change is bigger than your noise band."
NO_CHANGE_MESSAGE = "Reconsider before rebuying."
WORSE_MESSAGE = "Pause and look at what changed."
TOO_EARLY_MESSAGE = "Check back on day 14."
NO_BAND_MESSAGE = "Take 2 baseline captures first"
NEED_CHECKIN_MESSAGE = "Take your day-14 check-in"
NO_TARGETS_MESSAGE = "Pick at least one target aspect to get a verdict."
ALL_UNSTABLE_MESSAGE = (
    "Your target aspects are too noisy in your setup to judge; retake the baseline "
    "in steadier light"
)

CONFOUNDED_WARNING = (
    "Another product changed in this window; this verdict can't isolate one product."
)
MIXED_SOURCE_WARNING = "Captured different ways; differences may be larger."

D14 = "d14"
D28 = "d28"
BASELINE_WINDOW_DAYS = 7
D14_WINDOW = (12, 20)
D28_WINDOW = (26, 35)

_OUTSIDE = ("improved", "worse", "within_noise")


@dataclass(slots=True)
class TargetResult:
    """One target aspect, including why it was or was not used."""

    aspect: str
    baseline: float | None
    checkin: float | None
    delta: float | None
    band: float | None
    status: str
    note: str = ""


@dataclass(slots=True)
class Verdict:
    """The frozen outcome plus everything the verdict screen (P11) needs."""

    outcome: str
    message: str
    window: str
    day: int
    baseline_capture_ids: list[int]
    baseline_dates: list[str]
    checkin_capture_id: int | None
    checkin_date: str | None
    targets: list[TargetResult]
    top_changes: list[dict[str, object]]
    unstable_targets: list[dict[str, object]]
    mask_pairs: list[dict[str, object]]
    warnings: list[str]
    confounded: bool
    mixed_sources: bool
    label: str
    no_targets: bool = False
    all_targets_unstable: bool = False


def compute_verdict(
    product: object,
    captures: list[object],
    bands: dict[str, dict[str, object]],
    other_products: list[object],
    today: date | datetime | str,
) -> Verdict:
    """Apply plan §12 to one product and its person's captures.

    ``product`` and each capture may be a mapping or a sqlite3.Row. Captures need
    ``id``, a date (``captured_on`` or ``captured_at``), ``data_label``, ``source``,
    ``status`` and a ``scores`` mapping. ``bands`` is the dict returned by
    ``noise.get_bands``; an aspect with ``unstable`` true is never evaluated.
    """
    started = _as_date(_get(product, "started_on"))
    today_date = _as_date(today)
    day = (today_date - started).days
    target_aspects = _product_targets(product)
    baseline_captures = _baseline_captures(captures, started)
    baseline_dates = [_capture_date(capture) for capture in baseline_captures]
    band_map = bands if isinstance(bands, Mapping) else {}

    if not target_aspects:
        return _make_verdict(
            NO_BAND,
            NO_TARGETS_MESSAGE,
            window=D14,
            day=day,
            product=product,
            baseline_captures=baseline_captures,
            baseline_dates=baseline_dates,
            checkin_capture=None,
            targets=[],
            top_changes=[],
            warnings=[],
            confounded=False,
            mixed_sources=False,
            no_targets=True,
        )

    target_results = _target_results(
        target_aspects, band_map, baseline_captures, checkin_capture=None
    )
    entries = [(aspect, band_map.get(aspect)) for aspect in target_aspects]
    all_unstable = all(
        entry is not None and bool(entry.get("unstable")) for _, entry in entries
    )
    usable = [
        aspect
        for aspect, entry in entries
        if entry is not None and not bool(entry.get("unstable"))
    ]

    if not usable:
        message = ALL_UNSTABLE_MESSAGE if all_unstable else NO_BAND_MESSAGE
        return _make_verdict(
            NO_BAND,
            message,
            window=D14,
            day=day,
            product=product,
            baseline_captures=baseline_captures,
            baseline_dates=baseline_dates,
            checkin_capture=None,
            targets=target_results,
            top_changes=[],
            warnings=[],
            confounded=False,
            mixed_sources=False,
            all_targets_unstable=all_unstable,
        )

    if day < D14_WINDOW[0]:
        return _make_verdict(
            TOO_EARLY,
            TOO_EARLY_MESSAGE,
            window=D14,
            day=day,
            product=product,
            baseline_captures=baseline_captures,
            baseline_dates=baseline_dates,
            checkin_capture=None,
            targets=target_results,
            top_changes=[],
            warnings=[],
            confounded=False,
            mixed_sources=False,
        )

    checkin_capture, window = _select_checkin(captures, started, day)
    target_results = _target_results(
        target_aspects, band_map, baseline_captures, checkin_capture
    )
    if checkin_capture is None:
        return _make_verdict(
            NEED_CHECKIN,
            NEED_CHECKIN_MESSAGE,
            window=D14,
            day=day,
            product=product,
            baseline_captures=baseline_captures,
            baseline_dates=baseline_dates,
            checkin_capture=None,
            targets=target_results,
            top_changes=[],
            warnings=[],
            confounded=False,
            mixed_sources=False,
        )

    used_captures = [*baseline_captures, checkin_capture]
    confounded = _confounded(
        product, other_products, baseline_dates, _capture_date(checkin_capture)
    )
    mixed_sources = _mixed_sources(used_captures)
    warnings = []
    if confounded:
        warnings.append(CONFOUNDED_WARNING)
    if mixed_sources:
        warnings.append(MIXED_SOURCE_WARNING)

    evaluated = [target for target in target_results if target.status in _OUTSIDE]
    if not evaluated:
        return _make_verdict(
            NO_BAND,
            NO_BAND_MESSAGE,
            window=window,
            day=day,
            product=product,
            baseline_captures=baseline_captures,
            baseline_dates=baseline_dates,
            checkin_capture=checkin_capture,
            targets=target_results,
            top_changes=[],
            warnings=warnings,
            confounded=confounded,
            mixed_sources=mixed_sources,
        )

    if any(target.status == "worse" for target in evaluated):
        outcome, message = WORSE, WORSE_MESSAGE
    elif any(target.status == "improved" for target in evaluated):
        outcome, message = KEEP, KEEP_MESSAGE
    else:
        outcome, message = NO_CHANGE, NO_CHANGE_MESSAGE

    top_changes = _top_changes(baseline_captures, checkin_capture, band_map)
    label = _label(used_captures, product)
    mask_pairs = _mask_pairs(baseline_captures, checkin_capture, top_changes, label)
    return _make_verdict(
        outcome,
        message,
        window=window,
        day=day,
        product=product,
        baseline_captures=baseline_captures,
        baseline_dates=baseline_dates,
        checkin_capture=checkin_capture,
        targets=target_results,
        top_changes=top_changes,
        mask_pairs=mask_pairs,
        warnings=warnings,
        confounded=confounded,
        mixed_sources=mixed_sources,
        label=label,
    )


# -- input helpers -----------------------------------------------------------


def _get(item: object, key: str, default: object = None) -> object:
    if isinstance(item, Mapping):
        return item.get(key, default)
    try:
        return item[key]  # type: ignore[index]
    except (KeyError, IndexError, TypeError):
        return default


def _as_date(value: object) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _capture_date(capture: object) -> date:
    captured_on = _get(capture, "captured_on")
    if captured_on:
        return _as_date(captured_on)
    return _as_date(str(_get(capture, "captured_at", ""))[:10])


def _capture_id(capture: object) -> int:
    return int(_get(capture, "id", 0) or 0)


def _is_success(capture: object) -> bool:
    return str(_get(capture, "status", "success")) == "success"


def _score(capture: object, aspect: str) -> float | None:
    if capture is None:
        return None
    scores = _get(capture, "scores", {}) or {}
    if not isinstance(scores, Mapping):
        return None
    value = scores.get(aspect)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _product_targets(product: object) -> list[str]:
    raw = _get(product, "target_aspects", [])
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            return []
    if not isinstance(raw, (list, tuple)):
        return []
    targets: list[str] = []
    for value in raw:
        aspect = str(value)
        if aspect in NUMERIC_ASPECTS and aspect not in targets:
            targets.append(aspect)
    return targets


def _baseline_captures(captures: list[object], started: date) -> list[object]:
    """The 7-day pre-start captures, or the day-1 pair when the product starts then."""
    successes = [
        capture
        for capture in captures
        if _is_success(capture) and _capture_date_ok(capture)
    ]
    window_start = started - timedelta(days=BASELINE_WINDOW_DAYS)
    prior = [
        capture
        for capture in successes
        if window_start <= _capture_date(capture) < started
    ]
    if prior:
        return sorted(prior, key=lambda item: (_capture_date(item), _capture_id(item)))
    pair = [
        capture
        for capture in successes
        if _capture_date(capture) == started
        and bool(_get(capture, "is_baseline_pair", 0))
    ]
    return sorted(pair, key=lambda item: (_capture_date(item), _capture_id(item)))


def _capture_date_ok(capture: object) -> bool:
    try:
        _capture_date(capture)
        return True
    except (TypeError, ValueError):
        return False


def _select_checkin(
    captures: list[object], started: date, today_day: int
) -> tuple[object | None, str]:
    successes = [
        capture
        for capture in captures
        if _is_success(capture) and _capture_date_ok(capture)
    ]

    def closest(low: int, high: int, target: int) -> object | None:
        candidates = []
        for capture in successes:
            capture_day = (_capture_date(capture) - started).days
            if low <= capture_day <= high and capture_day <= today_day:
                candidates.append(
                    (
                        abs(capture_day - target),
                        capture_day,
                        _capture_date(capture),
                        _capture_id(capture),
                        capture,
                    )
                )
        if not candidates:
            return None
        return min(candidates, key=lambda item: item[:4])[-1]

    if today_day >= D28_WINDOW[0]:
        day_28 = closest(*D28_WINDOW, 28)
        if day_28 is not None:
            return day_28, D28
    day_14 = closest(*D14_WINDOW, 14)
    if day_14 is not None:
        return day_14, D14
    return None, D14


def _aspect_mean(captures: list[object], aspect: str) -> float | None:
    values = [
        value
        for value in (_score(capture, aspect) for capture in captures)
        if value is not None
    ]
    if not values:
        return None
    return round(sum(values) / len(values), 1)


# -- evaluation helpers ------------------------------------------------------


def _target_results(
    target_aspects: list[str],
    bands: Mapping[str, Mapping[str, object]],
    baseline_captures: list[object],
    checkin_capture: object | None,
) -> list[TargetResult]:
    results: list[TargetResult] = []
    for aspect in target_aspects:
        entry = bands.get(aspect)
        band = None if entry is None else float(entry["band"])
        baseline = _aspect_mean(baseline_captures, aspect)
        checkin = _score(checkin_capture, aspect)
        delta = (
            None
            if baseline is None or checkin is None
            else round(checkin - baseline, 1)
        )
        if entry is not None and bool(entry.get("unstable")):
            results.append(
                TargetResult(
                    aspect, baseline, checkin, delta, band, "unstable", "unstable, not used"
                )
            )
        elif entry is None:
            results.append(
                TargetResult(aspect, baseline, checkin, delta, None, "no_band", "no band")
            )
        elif baseline is None:
            results.append(
                TargetResult(
                    aspect, baseline, checkin, delta, band, "missing", "no baseline score"
                )
            )
        elif checkin_capture is None:
            results.append(
                TargetResult(
                    aspect, baseline, None, None, band, "pending", "check-in not taken"
                )
            )
        elif checkin is None:
            results.append(
                TargetResult(
                    aspect, baseline, checkin, delta, band, "missing", "no check-in score"
                )
            )
        elif delta > band:
            results.append(
                TargetResult(aspect, baseline, checkin, delta, band, "improved")
            )
        elif delta < -band:
            results.append(
                TargetResult(aspect, baseline, checkin, delta, band, "worse")
            )
        else:
            results.append(
                TargetResult(aspect, baseline, checkin, delta, band, "within_noise")
            )
    return results


def _top_changes(
    baseline_captures: list[object],
    checkin_capture: object,
    bands: Mapping[str, Mapping[str, object]],
) -> list[dict[str, object]]:
    """The 3 largest |Δ| across the stable numeric aspects, targets or not."""
    changes: list[dict[str, object]] = []
    for aspect in NUMERIC_ASPECTS:
        entry = bands.get(aspect)
        if entry is not None and bool(entry.get("unstable")):
            continue
        baseline = _aspect_mean(baseline_captures, aspect)
        checkin = _score(checkin_capture, aspect)
        if baseline is None or checkin is None:
            continue
        delta = round(checkin - baseline, 1)
        band = None if entry is None else float(entry["band"])
        if band is None:
            status, outside = "no_band", False
        elif delta > band:
            status, outside = "improved", True
        elif delta < -band:
            status, outside = "worse", True
        else:
            status, outside = "within_noise", False
        changes.append(
            {
                "aspect": aspect,
                "label": ASPECT_LABELS[aspect],
                "baseline": baseline,
                "checkin": checkin,
                "delta": delta,
                "direction": "up" if delta > 0 else "down" if delta < 0 else "flat",
                "band": band,
                "outside_band": outside,
                "status": status,
            }
        )
    changes.sort(key=lambda change: abs(float(change["delta"])), reverse=True)
    return changes[:3]


def _confounded(
    product: object,
    other_products: list[object],
    baseline_dates: list[date],
    checkin_date: date,
) -> bool:
    if not baseline_dates:
        return False
    first = min(baseline_dates)
    product_id = _get(product, "id")
    for other in other_products:
        if _get(other, "id") == product_id:
            continue
        for key in ("started_on", "ended_on"):
            value = _get(other, key)
            if not value:
                continue
            try:
                when = _as_date(value)
            except (TypeError, ValueError):
                continue
            if first <= when <= checkin_date:
                return True
    return False


def _mixed_sources(captures: list[object]) -> bool:
    sources = {str(_get(capture, "source", "")) for capture in captures}
    return "camera_kit" in sources and "upload" in sources


def _label(captures: list[object], product: object) -> str:
    labels = {str(_get(capture, "data_label", "REAL")) for capture in captures}
    if "SIMULATED" in labels:
        return "SIMULATED"
    if "SAMPLE" in labels:
        return "SAMPLE"
    if labels:
        return "REAL"
    return str(_get(product, "data_label", "REAL") or "REAL")


def _mask_pairs(
    baseline_captures: list[object],
    checkin_capture: object,
    top_changes: list[dict[str, object]],
    label: str,
) -> list[dict[str, object]]:
    """Before/after masks only when both compared captures are REAL and have them."""
    if label != "REAL" or not baseline_captures:
        return []
    before = max(
        baseline_captures, key=lambda capture: (_capture_date(capture), _capture_id(capture))
    )
    before_masks = _get(before, "masks", {}) or {}
    after_masks = _get(checkin_capture, "masks", {}) or {}
    if not isinstance(before_masks, Mapping) or not isinstance(after_masks, Mapping):
        return []
    pairs: list[dict[str, object]] = []
    for change in top_changes:
        aspect = str(change["aspect"])
        before_path = before_masks.get(aspect)
        after_path = after_masks.get(aspect)
        if before_path and after_path:
            pairs.append(
                {
                    "aspect": aspect,
                    "before_capture_id": _capture_id(before),
                    "after_capture_id": _capture_id(checkin_capture),
                    "before_path": before_path,
                    "after_path": after_path,
                }
            )
    return pairs


# -- result assembly ---------------------------------------------------------


def _make_verdict(
    outcome: str,
    message: str,
    *,
    window: str,
    day: int,
    product: object,
    baseline_captures: list[object],
    baseline_dates: list[date],
    checkin_capture: object | None,
    targets: list[TargetResult],
    top_changes: list[dict[str, object]],
    warnings: list[str],
    confounded: bool,
    mixed_sources: bool,
    label: str | None = None,
    mask_pairs: list[dict[str, object]] | None = None,
    no_targets: bool = False,
    all_targets_unstable: bool = False,
) -> Verdict:
    used = [*baseline_captures, *([checkin_capture] if checkin_capture is not None else [])]
    unstable = [
        {"aspect": target.aspect, "band": target.band, "note": target.note}
        for target in targets
        if target.status == "unstable"
    ]
    return Verdict(
        outcome=outcome,
        message=message,
        window=window,
        day=day,
        baseline_capture_ids=[_capture_id(capture) for capture in baseline_captures],
        baseline_dates=[value.isoformat() for value in baseline_dates],
        checkin_capture_id=(
            None if checkin_capture is None else _capture_id(checkin_capture)
        ),
        checkin_date=(
            None if checkin_capture is None else _capture_date(checkin_capture).isoformat()
        ),
        targets=targets,
        top_changes=top_changes,
        unstable_targets=unstable,
        mask_pairs=mask_pairs or [],
        warnings=warnings,
        confounded=confounded,
        mixed_sources=mixed_sources,
        label=label or _label(used, product),
        no_targets=no_targets,
        all_targets_unstable=all_targets_unstable,
    )
