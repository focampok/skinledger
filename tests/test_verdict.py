"""P10 acceptance tests: the frozen verdict engine with SAMPLE data only.

No images, no network and no web routes here: the engine is pure, and the one
store test uses a temporary SQLite database.
"""

from __future__ import annotations

import ast
import json
import logging
from datetime import date, timedelta
from pathlib import Path

import pytest

from skinledger import config, noise, verdict
from skinledger.aspects import NUMERIC_ASPECTS
from skinledger.db import connect, db_path, init_db
from skinledger.verdict_store import compute_for_product

# All fixture data in this module is SAMPLE.
START = "2026-10-10"
TODAY = date(2026, 10, 30)
D14_CHECKIN = "2026-10-24"


@pytest.fixture
def env(tmp_path, monkeypatch):
    settings = config.settings
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    monkeypatch.setattr(settings, "youcam_mock", True)
    init_db()
    return settings


def sample_scores(**overrides: float) -> dict[str, float]:
    values = {aspect: 50.0 for aspect in NUMERIC_ASPECTS}
    values.update(overrides)
    return values


def sample_capture(
    capture_id: int,
    captured_on: str,
    *,
    scores: dict[str, float] | None = None,
    data_label: str = "SAMPLE",
    source: str = "camera_kit",
    status: str = "success",
    baseline_pair: bool = False,
) -> dict[str, object]:
    return {
        "id": capture_id,
        "captured_on": captured_on,
        "data_label": data_label,
        "source": source,
        "status": status,
        "is_baseline_pair": int(baseline_pair),
        "scores": scores if scores is not None else sample_scores(),
    }


def sample_product(
    *,
    product_id: int = 1,
    started_on: str = START,
    targets: tuple[str, ...] = ("moisture",),
    ended_on: str | None = None,
) -> dict[str, object]:
    return {
        "id": product_id,
        "started_on": started_on,
        "ended_on": ended_on,
        "target_aspects": list(targets),
        "data_label": "SAMPLE",
    }


def sample_band(value: float) -> dict[str, object]:
    """Bands carry the flag noise.get_bands derives; the engine never recomputes it."""
    return {
        "band": float(value),
        "floor_applied": False,
        "unstable": noise.is_unstable(float(value)),
    }


def run(
    *,
    targets: tuple[str, ...] = ("moisture",),
    baseline: dict[str, float] | None = None,
    checkin: dict[str, float] | None = None,
    bands: dict[str, dict[str, object]] | None = None,
    today: date = TODAY,
    started_on: str = START,
    checkin_on: str = D14_CHECKIN,
    checkin_label: str = "SAMPLE",
    checkin_source: str = "camera_kit",
    other_products: list[object] | None = None,
    product_id: int = 1,
) -> verdict.Verdict:
    started = date.fromisoformat(started_on)
    baseline_on = (
        (started - timedelta(days=2)).isoformat(),
        (started - timedelta(days=1)).isoformat(),
    )
    captures = [
        sample_capture(1, baseline_on[0], scores=baseline or sample_scores()),
        sample_capture(2, baseline_on[1], scores=baseline or sample_scores()),
        sample_capture(
            3,
            checkin_on,
            scores=checkin or sample_scores(),
            data_label=checkin_label,
            source=checkin_source,
        ),
    ]
    return verdict.compute_verdict(
        sample_product(product_id=product_id, started_on=started_on, targets=targets),
        captures,
        bands if bands is not None else {"moisture": sample_band(4.0)},
        other_products or [],
        today,
    )


# -- (a)-(d): the three outcomes and the mixed case ---------------------------


def test_a_keep_when_moisture_improves_nine_points_over_a_band_of_four():
    result = run(
        baseline=sample_scores(moisture=50),
        checkin=sample_scores(moisture=59),
        bands={"moisture": sample_band(4.0)},
    )

    assert result.outcome == verdict.KEEP
    assert result.message == verdict.KEEP_MESSAGE
    assert result.targets[0].delta == 9.0
    assert result.targets[0].status == "improved"


def test_b_no_measurable_change_when_every_target_stays_inside_the_band():
    result = run(
        targets=("moisture", "pore"),
        checkin=sample_scores(moisture=52, pore=48),
        bands={"moisture": sample_band(4.0), "pore": sample_band(3.0)},
    )

    assert result.outcome == verdict.NO_CHANGE
    assert result.message == verdict.NO_CHANGE_MESSAGE
    assert [target.status for target in result.targets] == [
        "within_noise",
        "within_noise",
    ]


def test_c_worse_when_one_target_drops_six_points_past_a_band_of_three():
    result = run(
        targets=("acne",),
        checkin=sample_scores(acne=44),
        bands={"acne": sample_band(3.0)},
    )

    assert result.outcome == verdict.WORSE
    assert result.message == verdict.WORSE_MESSAGE
    assert result.targets[0].delta == -6.0
    assert result.targets[0].status == "worse"


def test_d_worse_wins_when_one_target_improves_and_another_worsens():
    result = run(
        targets=("moisture", "acne"),
        checkin=sample_scores(moisture=59, acne=44),
        bands={"moisture": sample_band(4.0), "acne": sample_band(3.0)},
    )

    assert result.outcome == verdict.WORSE
    assert {target.status for target in result.targets} == {"improved", "worse"}


# -- (e)-(j): timing, missing bands and warnings ------------------------------


def test_e_too_early_on_day_nine():
    result = run(
        today=date(2026, 10, 19),
        bands={"moisture": sample_band(4.0)},
    )

    assert result.day == 9
    assert result.outcome == verdict.TOO_EARLY
    assert result.message == verdict.TOO_EARLY_MESSAGE


def test_f_no_band_means_no_verdict():
    result = run(bands={})

    assert result.outcome == verdict.NO_BAND
    assert result.message == verdict.NO_BAND_MESSAGE
    assert result.targets[0].status == "no_band"


def test_g_another_product_starting_in_the_window_is_confounding():
    result = run(
        started_on="2026-10-01",
        checkin_on="2026-10-15",
        checkin=sample_scores(moisture=59),
        bands={"moisture": sample_band(4.0)},
        other_products=[
            {"id": 2, "started_on": "2026-10-05", "ended_on": None},
        ],
    )

    assert result.outcome == verdict.KEEP
    assert result.confounded is True
    assert verdict.CONFOUNDED_WARNING in result.warnings


def test_h_the_day_28_window_uses_the_day_27_capture_not_day_14():
    captures = [
        sample_capture(1, "2026-09-29"),
        sample_capture(2, "2026-09-30"),
        sample_capture(3, "2026-10-15", scores=sample_scores(moisture=70)),
        sample_capture(4, "2026-10-28", scores=sample_scores(moisture=52)),
    ]
    result = verdict.compute_verdict(
        sample_product(started_on="2026-10-01"),
        captures,
        {"moisture": sample_band(4.0)},
        [],
        date(2026, 10, 29),
    )

    assert result.window == verdict.D28
    assert result.checkin_capture_id == 4
    assert result.checkin_date == "2026-10-28"
    assert result.outcome == verdict.NO_CHANGE


def test_i_a_simulated_capture_makes_the_verdict_simulated():
    result = run(
        checkin=sample_scores(moisture=59),
        bands={"moisture": sample_band(4.0)},
        checkin_label="SIMULATED",
    )

    assert result.outcome == verdict.KEEP
    assert result.label == "SIMULATED"


def test_j_day_twelve_plus_without_a_window_capture_needs_a_checkin():
    captures = [
        sample_capture(1, "2026-10-08"),
        sample_capture(2, "2026-10-09"),
    ]
    result = verdict.compute_verdict(
        sample_product(),
        captures,
        {"moisture": sample_band(4.0)},
        [],
        date(2026, 10, 25),
    )

    assert result.outcome == verdict.NEED_CHECKIN
    assert result.message == verdict.NEED_CHECKIN_MESSAGE
    assert result.checkin_capture_id is None


# -- (k)-(m): edge, baseline mean and unstable aspects -----------------------


def test_k_a_change_exactly_equal_to_the_band_is_within_noise():
    result = run(
        checkin=sample_scores(moisture=54),
        bands={"moisture": sample_band(4.0)},
    )

    assert result.targets[0].delta == 4.0
    assert result.targets[0].status == "within_noise"
    assert result.outcome == verdict.NO_CHANGE


def test_l_three_baseline_captures_are_averaged():
    captures = [
        sample_capture(1, "2026-10-04", scores=sample_scores(moisture=40)),
        sample_capture(2, "2026-10-06", scores=sample_scores(moisture=50)),
        sample_capture(3, "2026-10-09", scores=sample_scores(moisture=60)),
        sample_capture(4, D14_CHECKIN, scores=sample_scores(moisture=55)),
    ]
    result = verdict.compute_verdict(
        sample_product(),
        captures,
        {"moisture": sample_band(4.0)},
        [],
        date(2026, 10, 25),
    )

    assert result.baseline_capture_ids == [1, 2, 3]
    assert result.targets[0].baseline == 50.0
    assert result.targets[0].delta == 5.0
    assert result.outcome == verdict.KEEP


def test_m_unstable_targets_are_excluded_and_all_unstable_just_says_noisy():
    # One unstable target: pore's 12-point band hides a 20-point drop.
    one_unstable = run(
        targets=("moisture", "pore"),
        checkin=sample_scores(moisture=51, pore=30),
        bands={"moisture": sample_band(3.0), "pore": sample_band(12.0)},
    )

    assert one_unstable.outcome == verdict.NO_CHANGE
    assert one_unstable.unstable_targets == [
        {"aspect": "pore", "band": 12.0, "note": "unstable, not used"}
    ]
    pore = next(target for target in one_unstable.targets if target.aspect == "pore")
    assert pore.status == "unstable"
    assert pore.note == "unstable, not used"
    assert all(change["aspect"] != "pore" for change in one_unstable.top_changes)

    # Every target unstable: no_band with the "too noisy" message and flag.
    all_unstable = run(
        targets=("moisture", "pore"),
        checkin=sample_scores(moisture=70, pore=30),
        bands={"moisture": sample_band(12.0), "pore": sample_band(12.0)},
    )

    assert all_unstable.outcome == verdict.NO_BAND
    assert all_unstable.all_targets_unstable is True
    assert all_unstable.message == verdict.ALL_UNSTABLE_MESSAGE


# -- zero targets ------------------------------------------------------------


def test_a_product_with_no_targets_gets_the_pick_a_target_message():
    result = run(targets=(), bands={"moisture": sample_band(4.0)})

    assert result.outcome == verdict.NO_BAND
    assert result.no_targets is True
    assert result.message == verdict.NO_TARGETS_MESSAGE
    assert result.targets == []


def test_no_targets_wins_even_with_bands_a_checkin_and_a_full_day_count():
    result = run(
        targets=(),
        checkin=sample_scores(moisture=70),
        bands={"moisture": sample_band(4.0)},
    )

    assert result.outcome == verdict.NO_BAND
    assert result.no_targets is True
    assert result.all_targets_unstable is False


# -- purity and persistence --------------------------------------------------


def test_the_verdict_module_imports_nothing_from_web_or_the_database():
    source = Path(verdict.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)

    forbidden = {
        "sqlite3",
        "skinledger.db",
        "skinledger.web",
        "skinledger.noise",
        "skinledger.verdict_store",
    }
    assert not {
        module
        for module in modules
        if module in forbidden
        or module.startswith("skinledger.web.")
        or module.startswith("skinledger.db.")
    }


def test_mask_pairs_only_when_both_captures_are_real_and_have_masks():
    captures = [
        sample_capture(1, "2026-10-08", data_label="REAL"),
        sample_capture(2, "2026-10-09", data_label="REAL"),
        sample_capture(
            3, D14_CHECKIN, data_label="REAL", scores=sample_scores(moisture=59)
        ),
    ]
    captures[1]["masks"] = {"moisture": "masks/1/before_moisture.png"}
    captures[2]["masks"] = {"moisture": "masks/1/after_moisture.png"}
    result = verdict.compute_verdict(
        sample_product(),
        captures,
        {"moisture": sample_band(4.0)},
        [],
        TODAY,
    )

    assert result.label == "REAL"
    assert result.mask_pairs == [
        {
            "aspect": "moisture",
            "before_capture_id": 2,
            "after_capture_id": 3,
            "before_path": "masks/1/before_moisture.png",
            "after_path": "masks/1/after_moisture.png",
        }
    ]
    # SAMPLE captures never expose masks, even if a path were attached.
    assert run().mask_pairs == []


def test_mixed_upload_and_camera_kit_captures_warn_about_the_comparison():
    result = run(
        checkin=sample_scores(moisture=59),
        bands={"moisture": sample_band(4.0)},
        checkin_source="upload",
    )

    assert result.mixed_sources is True
    assert verdict.MIXED_SOURCE_WARNING in result.warnings


def _seed_store_rows(
    *, with_checkin: bool = True, target_aspects: str = '["moisture"]'
) -> tuple[int, int]:
    conn = connect(db_path())
    try:
        person_id = int(
            conn.execute(
                "INSERT INTO persons (display_name, owner_token_hash) "
                "VALUES ('Self', 'hash')"
            ).lastrowid
        )
        product_id = int(
            conn.execute(
                "INSERT INTO products (person_id, name, category, started_on, "
                "target_aspects, data_label) VALUES (?, 'Serum (SAMPLE)', 'serum', "
                "'2026-10-01', ?, 'SAMPLE')",
                (person_id, target_aspects),
            ).lastrowid
        )
        baseline = [
            ("2026-10-01T15:00:00.000Z", 1),
            ("2026-10-01T16:00:00.000Z", 1),
        ]
        for captured_at, pair in baseline:
            capture_id = conn.execute(
                "INSERT INTO captures (person_id, owner_token_hash, captured_at, "
                "data_label, source, status, is_baseline_pair) "
                "VALUES (?, 'hash', ?, 'SAMPLE', 'camera_kit', 'success', ?)",
                (person_id, captured_at, pair),
            ).lastrowid
            conn.execute(
                "INSERT INTO aspect_scores (capture_id, aspect, raw_score) "
                "VALUES (?, 'moisture', 50)",
                (capture_id,),
            )
        if with_checkin:
            capture_id = conn.execute(
                "INSERT INTO captures (person_id, owner_token_hash, captured_at, "
                "data_label, source, status, is_baseline_pair) "
                "VALUES (?, 'hash', '2026-10-15T15:00:00.000Z', 'SAMPLE', "
                "'camera_kit', 'success', 0)",
                (person_id,),
            ).lastrowid
            conn.execute(
                "INSERT INTO aspect_scores (capture_id, aspect, raw_score) "
                "VALUES (?, 'moisture', 59)",
                (capture_id,),
            )
        conn.commit()
        noise.compute_band(person_id, conn=conn)
    finally:
        conn.close()
    return person_id, product_id


def test_the_store_writes_payload_json_and_logs_only_ids_outcome_and_flags(
    env, caplog
):
    _, product_id = _seed_store_rows()
    conn = connect(db_path())
    try:
        with caplog.at_level(logging.INFO, logger="skinledger.events"):
            result = compute_for_product(
                conn, product_id, today=date(2026, 10, 16)
            )
        row = conn.execute(
            "SELECT * FROM verdicts WHERE product_id = ?", (product_id,)
        ).fetchone()
    finally:
        conn.close()

    assert result is not None
    assert result.outcome == verdict.KEEP
    assert row["outcome"] == "keep"
    assert row["check_window"] == "d14"
    assert "ui_score" not in row["payload_json"]
    payload = json.loads(row["payload_json"])
    assert payload["outcome"] == "keep"
    assert payload["label"] == "SAMPLE"
    assert payload["targets"][0]["aspect"] == "moisture"

    messages = [
        record.getMessage()
        for record in caplog.records
        if "verdict.computed" in record.getMessage()
    ]
    assert len(messages) == 1
    assert f"product_id={product_id}" in messages[0]
    assert "outcome=keep" in messages[0]
    assert "flags=none" in messages[0]
    assert "Serum" not in messages[0]


def test_the_store_persists_zero_target_products_as_no_band(env):
    _, product_id = _seed_store_rows(target_aspects="[]")
    conn = connect(db_path())
    try:
        result = compute_for_product(conn, product_id, today=date(2026, 10, 16))
        row = conn.execute(
            "SELECT outcome, payload_json FROM verdicts WHERE product_id = ?",
            (product_id,),
        ).fetchone()
    finally:
        conn.close()

    assert result is not None
    assert result.no_targets is True
    assert row["outcome"] == "no_band"
    assert json.loads(row["payload_json"])["no_targets"] is True


def test_the_store_does_not_persist_the_transient_need_checkin_state(env):
    _, product_id = _seed_store_rows(with_checkin=False)
    conn = connect(db_path())
    try:
        result = compute_for_product(conn, product_id, today=date(2026, 10, 16))
        count = conn.execute("SELECT COUNT(*) FROM verdicts").fetchone()[0]
    finally:
        conn.close()

    assert result is not None
    assert result.outcome == verdict.NEED_CHECKIN
    assert count == 0
