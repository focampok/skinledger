"""P08 acceptance tests: per-aspect timeline page, series JSON and chart assets.

All data is SAMPLE and inserted straight into SQLite; no images are used.
"""

from __future__ import annotations

import html
import json
import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from skinledger import config, copy, guards, noise, pipeline
from skinledger.aspects import NUMERIC_ASPECTS
from skinledger.db import connect, db_path, init_db
from skinledger.web.app import app

OWNER_TOKEN = "owner-token"
OTHER_TOKEN = "other-token"
T1 = "2026-10-28T10:00:00.000Z"
T2 = "2026-10-28T10:03:00.000Z"
T3 = "2026-10-29T10:00:00.000Z"

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src/skinledger/web/static"
TEMPLATES = ROOT / "src/skinledger/web/templates"


@pytest.fixture
def env(tmp_path, monkeypatch):
    settings = config.settings
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    monkeypatch.setattr(settings, "youcam_mock", True)
    monkeypatch.setattr(settings, "invite_code", SecretStr("invite-ok"))
    monkeypatch.setattr(settings, "admin_token", SecretStr("admin-ok"))
    monkeypatch.setattr(pipeline, "get_client", lambda: None)
    init_db()
    return settings


@pytest.fixture
def web(env):
    with TestClient(app, base_url="https://testserver") as client:
        yield client


# -- helpers -----------------------------------------------------------------


def seed_person(*, token: str = OWNER_TOKEN, name: str = "Self") -> int:
    conn = connect(db_path())
    try:
        person_id = conn.execute(
            "INSERT INTO persons (display_name, owner_token_hash) VALUES (?, ?)",
            (name, guards.owner_token_hash(token)),
        ).lastrowid
        conn.commit()
        return int(person_id or 0)
    finally:
        conn.close()


def add_capture(
    person_id: int,
    *,
    at: str,
    source: str = "camera_kit",
    data_label: str = "SAMPLE",
    baseline: bool = True,
    token: str = OWNER_TOKEN,
) -> int:
    conn = connect(db_path())
    try:
        capture_id = conn.execute(
            "INSERT INTO captures (person_id, owner_token_hash, captured_at, data_label, "
            "source, status, is_baseline_pair) VALUES (?, ?, ?, ?, ?, 'success', ?)",
            (
                person_id,
                guards.owner_token_hash(token),
                at,
                data_label,
                source,
                int(baseline),
            ),
        ).lastrowid
        conn.commit()
        return int(capture_id or 0)
    finally:
        conn.close()


def add_scores(
    capture_id: int,
    scores: dict[str, float] | None = None,
    values: dict[str, str] | None = None,
) -> None:
    conn = connect(db_path())
    try:
        for aspect, score in (scores or {}).items():
            conn.execute(
                "INSERT INTO aspect_scores (capture_id, aspect, raw_score) VALUES (?, ?, ?)",
                (capture_id, aspect, score),
            )
        for aspect, text in (values or {}).items():
            conn.execute(
                "INSERT INTO aspect_scores (capture_id, aspect, value_text) VALUES (?, ?, ?)",
                (capture_id, aspect, text),
            )
        conn.commit()
    finally:
        conn.close()


def add_product(
    person_id: int,
    *,
    name: str = "Niacinamide serum (SAMPLE)",
    targets: list[str] | None = None,
    started_on: str = "2026-10-28",
    ended_on: str | None = None,
) -> int:
    conn = connect(db_path())
    try:
        product_id = conn.execute(
            "INSERT INTO products (person_id, name, category, started_on, ended_on, "
            "target_aspects, data_label) VALUES (?, ?, 'serum', ?, ?, ?, 'SAMPLE')",
            (person_id, name, started_on, ended_on, json.dumps(targets or [])),
        ).lastrowid
        conn.commit()
        return int(product_id or 0)
    finally:
        conn.close()


def seed_baseline_pair(
    person_id: int,
    *,
    first: float = 50.0,
    second: float = 52.0,
    overrides_first: dict[str, float] | None = None,
    overrides_second: dict[str, float] | None = None,
) -> tuple[int, int, int]:
    """Two SAMPLE captures covering all 15 aspects, then the stored day-1 band."""
    scores_a = {aspect: first for aspect in NUMERIC_ASPECTS}
    scores_b = {aspect: second for aspect in NUMERIC_ASPECTS}
    scores_a.update(overrides_first or {})
    scores_b.update(overrides_second or {})
    capture_a = add_capture(person_id, at=T1)
    add_scores(capture_a, scores_a, {"skin_type_whole": "Combination"})
    capture_b = add_capture(person_id, at=T2)
    add_scores(capture_b, scores_b, {"skin_type_whole": "Combination"})
    third = add_capture(person_id, at=T3, baseline=False)
    add_scores(third, {aspect: 60.0 for aspect in NUMERIC_ASPECTS})
    noise.compute_band(person_id)
    return capture_a, capture_b, third


def login(client: TestClient, token: str = OWNER_TOKEN) -> None:
    client.cookies.set(guards.OWNER_COOKIE, guards.encode_owner_cookie(token))


def series(web: TestClient, person_id: int) -> dict:
    response = web.get(f"/api/people/{person_id}/series")
    assert response.status_code == 200
    return response.json()


def aspects_by_name(data: dict) -> dict[str, dict]:
    return {aspect["aspect"]: aspect for aspect in data["aspects"]}


# -- page --------------------------------------------------------------------


def test_timeline_page_renders_15_cards_and_the_skin_type_chip(env, web):
    person_id = seed_person()
    seed_baseline_pair(person_id)
    login(web)

    response = web.get(f"/people/{person_id}/timeline")

    assert response.status_code == 200
    assert response.text.count("data-timeline-aspect=") == 15
    for aspect in NUMERIC_ASPECTS:
        assert f'data-timeline-aspect="{aspect}"' in response.text
    assert 'data-skin-type="Combination"' in response.text
    assert copy.TIMELINE_TITLE in response.text
    assert copy.TIMELINE_BAND_LEGEND in response.text
    assert copy.DISCLAIMER in response.text
    assert f'href="/people/{person_id}/capture"' in response.text


def test_series_json_has_no_ui_score_and_uses_raw_points(env, web):
    person_id = seed_person()
    seed_baseline_pair(person_id)
    login(web)

    data = series(web, person_id)

    assert "ui_score" not in json.dumps(data)
    assert data["has_band"] is True
    assert len(data["aspects"]) == 15
    points = data["aspects"][0]["points"]
    assert points
    assert set(points[0]) == {"t", "raw_score", "data_label", "source", "capture_id"}
    assert points[0]["t"] == T1
    assert points[0]["raw_score"] == 50.0
    assert points[0]["data_label"] == "SAMPLE"
    assert points[0]["source"] == "camera_kit"
    assert data["skin_type"]["value"] == "Combination"
    assert data["skin_type"]["data_label"] == "SAMPLE"


def test_an_unstable_band_sorts_last_and_a_stable_band_does_not(env, web):
    person_id = seed_person()
    # acne moves 12 points between the two day-1 captures; every other aspect moves 2.
    seed_baseline_pair(
        person_id,
        overrides_first={"acne": 60.0},
        overrides_second={"acne": 48.0},
    )
    login(web)

    data = series(web, person_id)
    by_name = aspects_by_name(data)

    assert by_name["acne"]["band"] == 12.0
    assert by_name["acne"]["unstable"] is True
    assert by_name["moisture"]["band"] == 3.0
    assert by_name["moisture"]["unstable"] is False
    assert data["aspects"][-1]["aspect"] == "acne"
    assert data["aspects"][-1]["group"] == "unstable"

    page = web.get(f"/people/{person_id}/timeline").text
    assert page.count(copy.TIMELINE_UNSTABLE_CHIP) == 1
    assert copy.TIMELINE_UNSTABLE_NOTE in html.unescape(page)
    assert page.rindex('data-timeline-aspect="acne"') > page.index(
        'data-timeline-aspect="moisture"'
    )


def test_a_person_without_a_band_gets_the_banner_and_null_bands(env, web):
    person_id = seed_person()
    capture = add_capture(person_id, at=T1)
    add_scores(capture, {aspect: 40.0 for aspect in NUMERIC_ASPECTS})
    login(web)

    data = series(web, person_id)
    assert data["has_band"] is False
    assert all(aspect["band"] is None for aspect in data["aspects"])
    assert all(aspect["baseline"] is None for aspect in data["aspects"])

    page = web.get(f"/people/{person_id}/timeline").text
    assert 'data-has-band="false"' in page
    assert copy.NO_BAND_YET in page
    assert f'href="/people/{person_id}/capture"' in page
    assert copy.TIMELINE_BAND_LEGEND not in page


def test_active_product_targets_come_first(env, web):
    person_id = seed_person()
    seed_baseline_pair(person_id)
    add_product(person_id, targets=["oiliness", "pore"])
    add_product(
        person_id,
        name="Ended product (SAMPLE)",
        targets=["acne"],
        started_on="2026-10-01",
        ended_on="2026-10-20",
    )
    login(web)

    data = series(web, person_id)

    assert [aspect["aspect"] for aspect in data["aspects"][:2]] == ["oiliness", "pore"]
    assert [aspect["group"] for aspect in data["aspects"][:2]] == ["target", "target"]
    assert len(data["products"]) == 2


def test_another_browser_gets_404_on_page_and_endpoint(env, web):
    person_id = seed_person()
    seed_baseline_pair(person_id)
    login(web, OTHER_TOKEN)

    assert web.get(f"/people/{person_id}/timeline").status_code == 404
    assert web.get(f"/api/people/{person_id}/series").status_code == 404


# -- assets ------------------------------------------------------------------


def test_timeline_loads_chartjs_locally_and_has_no_external_urls(env, web):
    template = (TEMPLATES / "timeline.html").read_text(encoding="utf-8")
    charts_js = (STATIC / "charts.js").read_text(encoding="utf-8")

    assert 'src="/static/vendor/chart.umd.min.js"' in template
    assert (STATIC / "vendor" / "chart.umd.min.js").is_file()
    for source in (template, charts_js):
        assert "http://" not in source
        assert "https://" not in source
        assert "cdn." not in source
    assert "ui_score" not in charts_js
    assert 'fill: "-1"' in charts_js
    assert "borderDash" in charts_js
    assert "pointBackgroundColor" in charts_js
    assert '"guided camera"' in charts_js
    assert '"upload"' in charts_js
    assert "slProductMarks" in charts_js
    assert "started_on" in charts_js


def test_chart_js_is_not_loaded_on_other_pages(env, web):
    assert "chart.umd.min.js" not in web.get("/").text
    assert 'script src="/static/vendor/chart.umd.min.js"' in (
        TEMPLATES / "timeline.html"
    ).read_text(encoding="utf-8")


def test_the_timeline_grid_collapses_to_one_column_on_a_phone():
    css = (STATIC / "app.css").read_text(encoding="utf-8")
    base_rule = css.split(".timeline-grid {", 1)[1].split("}", 1)[0]

    assert "grid-template-columns: minmax(0, 1fr)" in base_rule
    assert "repeat(" not in base_rule
    assert "@media (min-width: 640px)" in css
    assert "min-width: 0" in css.split(".timeline-card {", 1)[1].split("}", 1)[0]


def test_the_person_and_baseline_pages_link_to_the_timeline(env, web):
    person_id = seed_person()
    seed_baseline_pair(person_id)
    login(web)
    link = f'href="/people/{person_id}/timeline"'

    assert link in web.get("/people").text
    assert link in web.get(f"/people/{person_id}/baseline").text


# -- logging -----------------------------------------------------------------


def test_viewing_the_timeline_logs_only_person_and_aspect_count(env, web, caplog):
    person_id = seed_person(name="Private Name")
    seed_baseline_pair(person_id)
    login(web)

    with caplog.at_level(logging.INFO, logger="skinledger.events"):
        assert web.get(f"/people/{person_id}/timeline").status_code == 200

    messages = [record.getMessage() for record in caplog.records]
    viewed = [message for message in messages if "timeline.viewed" in message]
    assert len(viewed) == 1
    assert f"person_id={person_id}" in viewed[0]
    assert "aspect_count=15" in viewed[0]
    assert "Private Name" not in viewed[0]
