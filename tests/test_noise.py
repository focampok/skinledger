"""P07 acceptance tests: per-aspect noise band, unstable aspects and the baseline page."""

from __future__ import annotations

import asyncio
import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import SecretStr

from skinledger import config, copy, guards, noise, pipeline, usage
from skinledger.aspects import NUMERIC_ASPECTS
from skinledger.db import connect, db_path, init_db
from skinledger.web.app import app
from skinledger.youcam import TaskResult

OWNER_TOKEN = "owner-token"
OTHER_TOKEN = "other-token"
INVITE = "invite-ok"

T1 = "2026-10-28T10:00:00.000Z"
T2 = "2026-10-28T10:03:00.000Z"
T3 = "2026-10-28T11:00:00.000Z"
T4 = "2026-10-28T11:03:00.000Z"


def grey_png() -> bytes:
    buffer = io.BytesIO()
    Image.new("L", (16, 16), color=200).save(buffer, format="PNG")
    return buffer.getvalue()


def sample_result() -> TaskResult:
    return TaskResult(
        status="success",
        scores={aspect: 50.0 for aspect in NUMERIC_ASPECTS},
        categorical={"skin_type_whole": "Combination"},
        mask_urls={},
        raw={"data": {"task_status": "success", "results": {"output": []}}},
    )


class StubClient:
    async def upload_file(self, img, file_name="capture.jpg") -> str:
        return "file-stub"

    async def create_task(self, file_id, actions=None, mask_overlay=False) -> str:
        return "task-stub"

    async def poll(self, task_id, interval=None, timeout=None) -> TaskResult:
        return sample_result()

    async def download(self, url: str, task_id: str | None = None) -> bytes:
        return grey_png()


@pytest.fixture
def env(tmp_path, monkeypatch):
    settings = config.settings
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    monkeypatch.setattr(settings, "youcam_mock", True)
    monkeypatch.setattr(settings, "store_masks", False)
    monkeypatch.setattr(settings, "invite_code", SecretStr(INVITE))
    monkeypatch.setattr(settings, "admin_token", SecretStr("admin-ok"))
    monkeypatch.setattr(settings, "max_real_analyses_per_person", 4)
    monkeypatch.setattr(settings, "daily_unit_cap", 96)
    monkeypatch.setattr(settings, "total_unit_cap", 480)
    monkeypatch.setattr(settings, "units_per_analysis", 16)
    monkeypatch.setattr(pipeline, "get_client", lambda: StubClient())
    init_db()
    return settings


@pytest.fixture
def web(env):
    with TestClient(app, base_url="https://testserver") as client:
        yield client


# -- helpers -----------------------------------------------------------------


def seed_person(*, token: str = OWNER_TOKEN, name: str = "Self", consent: bool = True) -> int:
    conn = connect(db_path())
    try:
        person_id = conn.execute(
            "INSERT INTO persons (display_name, owner_token_hash) VALUES (?, ?)",
            (name, guards.owner_token_hash(token)),
        ).lastrowid
        if consent:
            conn.execute(
                "INSERT INTO consents (person_id, consent_version, adult_confirmed, accepted_at) "
                "VALUES (?, ?, 1, ?)",
                (person_id, copy.CONSENT_VERSION, usage.utc_now_iso()),
            )
        conn.commit()
        return int(person_id or 0)
    finally:
        conn.close()


def add_capture(
    person_id: int,
    *,
    at: str,
    source: str = "camera_kit",
    baseline: bool = True,
    status: str = "success",
    task_id: str | None = None,
    token: str = OWNER_TOKEN,
) -> int:
    conn = connect(db_path())
    try:
        capture_id = conn.execute(
            "INSERT INTO captures (person_id, owner_token_hash, captured_at, data_label, source, "
            "status, task_id, is_baseline_pair) VALUES (?, ?, ?, 'SAMPLE', ?, ?, ?, ?)",
            (
                person_id,
                guards.owner_token_hash(token),
                at,
                source,
                status,
                task_id,
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


def seed_pair(
    person_id: int,
    scores_a: dict[str, float],
    scores_b: dict[str, float],
    *,
    source_a: str = "camera_kit",
    source_b: str = "camera_kit",
    values_a: dict[str, str] | None = None,
    values_b: dict[str, str] | None = None,
    at_a: str = T1,
    at_b: str = T2,
) -> tuple[int, int]:
    first = add_capture(person_id, at=at_a, source=source_a)
    add_scores(first, scores_a, values_a)
    second = add_capture(person_id, at=at_b, source=source_b)
    add_scores(second, scores_b, values_b)
    return first, second


def login(client: TestClient, token: str = OWNER_TOKEN) -> None:
    client.cookies.set(guards.OWNER_COOKIE, guards.encode_owner_cookie(token))


def band_rows(person_id: int) -> list[dict]:
    conn = connect(db_path())
    try:
        rows = conn.execute(
            "SELECT aspect, band, a_capture_id, b_capture_id, floor_applied FROM noise_bands "
            "WHERE person_id = ? ORDER BY aspect",
            (person_id,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


# -- bands -------------------------------------------------------------------


def test_a_two_point_difference_is_floored_at_three_points(env):
    person_id = seed_person()
    seed_pair(person_id, {"acne": 60.0}, {"acne": 58.0})

    report = noise.compute_band(person_id)

    assert report is not None
    assert report.bands["acne"] == {"band": 3.0, "floor_applied": True, "unstable": False}
    assert noise.get_bands(person_id)["acne"] == {
        "band": 3.0,
        "floor_applied": True,
        "unstable": False,
    }


def test_a_measured_eight_point_difference_is_stable(env):
    person_id = seed_person()
    seed_pair(person_id, {"moisture": 70.0}, {"moisture": 62.0})

    report = noise.compute_band(person_id)

    assert report is not None
    assert report.bands["moisture"] == {
        "band": 8.0,
        "floor_applied": False,
        "unstable": False,
    }


def test_a_seventeen_point_difference_is_unstable(env):
    person_id = seed_person()
    seed_pair(person_id, {"pore": 53.2}, {"pore": 35.9})

    report = noise.compute_band(person_id)

    assert report is not None
    assert report.bands["pore"] == {"band": 17.3, "floor_applied": False, "unstable": True}
    assert noise.get_bands(person_id)["pore"]["unstable"] is True


def test_an_aspect_missing_from_one_capture_has_no_band(env):
    person_id = seed_person()
    seed_pair(person_id, {"acne": 60.0, "moisture": 40.0}, {"acne": 58.0})

    report = noise.compute_band(person_id)

    assert report is not None
    assert set(report.bands) == {"acne"}
    assert "moisture" not in noise.get_bands(person_id)


def test_a_new_pair_replaces_the_previous_band(env):
    person_id = seed_person()
    seed_pair(person_id, {"acne": 60.0}, {"acne": 50.0})
    noise.compute_band(person_id)
    assert noise.get_bands(person_id)["acne"]["band"] == 10.0

    first, second = seed_pair(
        person_id, {"acne": 40.0}, {"acne": 38.0}, at_a=T3, at_b=T4
    )
    report = noise.compute_band(person_id)

    assert report is not None
    assert report.a_capture_id == first
    assert report.b_capture_id == second
    rows = band_rows(person_id)
    assert [(row["aspect"], row["band"]) for row in rows] == [("acne", 3.0)]
    assert rows[0]["a_capture_id"] == first


def test_mixed_sources_add_a_note(env):
    person_id = seed_person()
    seed_pair(
        person_id,
        {"acne": 60.0},
        {"acne": 58.0},
        source_a="camera_kit",
        source_b="upload",
    )

    report = noise.compute_band(person_id)

    assert report is not None
    assert noise.MIXED_SOURCE_NOTE in report.notes
    assert noise.read_band_report(person_id).notes == [noise.MIXED_SOURCE_NOTE]


def test_same_source_pairs_have_no_mixed_note(env):
    person_id = seed_person()
    seed_pair(person_id, {"acne": 60.0}, {"acne": 58.0})

    report = noise.compute_band(person_id)

    assert report is not None
    assert report.notes == []


def test_a_changed_skin_type_adds_a_note(env):
    person_id = seed_person()
    seed_pair(
        person_id,
        {"acne": 60.0},
        {"acne": 58.0},
        values_a={"skin_type_whole": "Combination"},
        values_b={"skin_type_whole": "Oily"},
    )

    report = noise.compute_band(person_id)

    assert report is not None
    assert noise.SKIN_TYPE_NOTE in report.notes
    # skin_type is categorical: it never gets a band of its own.
    assert not any(aspect.startswith("skin_type") for aspect in report.bands)


def test_an_unchanged_skin_type_adds_no_note(env):
    person_id = seed_person()
    seed_pair(
        person_id,
        {"acne": 60.0},
        {"acne": 58.0},
        values_a={"skin_type_whole": "Combination"},
        values_b={"skin_type_whole": "Combination"},
    )

    report = noise.compute_band(person_id)

    assert report is not None
    assert report.notes == []


def test_recompute_all_recomputes_twice_with_the_same_result(env):
    first_person = seed_person(name="First")
    second_person = seed_person(name="Second")
    loner = seed_person(name="No pair")
    seed_pair(first_person, {"acne": 60.0}, {"acne": 58.0})
    seed_pair(second_person, {"pore": 53.2}, {"pore": 35.9})
    add_capture(loner, at=T1)

    assert noise.recompute_all() == 2
    before = {person: band_rows(person) for person in (first_person, second_person, loner)}

    assert noise.recompute_all() == 2
    after = {person: band_rows(person) for person in (first_person, second_person, loner)}

    assert before == after
    assert before[loner] == []
    assert noise.get_bands(second_person)["pore"]["unstable"] is True


def test_the_second_baseline_success_writes_the_band(env, monkeypatch):
    person_id = seed_person()
    first = add_capture(person_id, at=T1, status="running", task_id="task-1")

    asyncio.run(pipeline.finish_analysis(first))

    assert noise.get_bands(person_id) == {}

    second = add_capture(person_id, at=T2, status="running", task_id="task-2")
    asyncio.run(pipeline.finish_analysis(second))

    bands = noise.get_bands(person_id)
    assert set(bands) == set(NUMERIC_ASPECTS)
    assert all(values["band"] == 3.0 and values["floor_applied"] for values in bands.values())


# -- /people/{id}/baseline ---------------------------------------------------


def test_baseline_page_shows_both_captures_bands_and_status(env, web):
    person_id = seed_person()
    seed_pair(person_id, {"acne": 60.0, "moisture": 70.0}, {"acne": 58.0, "moisture": 62.0})
    noise.compute_band(person_id)
    login(web)

    response = web.get(f"/people/{person_id}/baseline")

    assert response.status_code == 200
    assert "Aspect" in response.text
    assert "Capture 1" in response.text
    assert "Capture 2" in response.text
    assert "Noise band" in response.text
    assert "Acne" in response.text
    assert "3.0" in response.text
    assert "8.0" in response.text
    assert "Stable" in response.text
    assert "Unstable for your setup" not in response.text
    assert copy.BASELINE_INTRO in response.text
    assert "SAMPLE" in response.text
    assert copy.DISCLAIMER in response.text


def test_baseline_page_marks_unstable_aspects_and_explains_them(env, web):
    person_id = seed_person()
    seed_pair(person_id, {"pore": 53.2}, {"pore": 35.9})
    noise.compute_band(person_id)
    login(web)

    response = web.get(f"/people/{person_id}/baseline")

    assert response.status_code == 200
    assert "17.3" in response.text
    assert "Unstable for your setup" in response.text
    assert copy.BASELINE_UNSTABLE_HINT in response.text


def test_baseline_page_shows_the_skin_type_and_mixed_source_notes(env, web):
    person_id = seed_person()
    seed_pair(
        person_id,
        {"acne": 60.0},
        {"acne": 58.0},
        source_b="upload",
        values_a={"skin_type_whole": "Combination"},
        values_b={"skin_type_whole": "Oily"},
    )
    noise.compute_band(person_id)
    login(web)

    response = web.get(f"/people/{person_id}/baseline")

    assert response.status_code == 200
    assert noise.SKIN_TYPE_NOTE in response.text
    assert noise.MIXED_SOURCE_NOTE in response.text


def test_baseline_page_without_a_pair_asks_for_two_captures(env, web):
    person_id = seed_person()
    login(web)

    response = web.get(f"/people/{person_id}/baseline")

    assert response.status_code == 200
    assert copy.NO_BAND_YET in response.text
    assert "Noise band" not in response.text


def test_baseline_page_is_hidden_from_another_browser(env, web):
    person_id = seed_person()
    login(web, OTHER_TOKEN)

    assert web.get(f"/people/{person_id}/baseline").status_code == 404


def test_capture_result_links_to_the_baseline_after_the_second_capture(env, web):
    person_id = seed_person()
    seed_pair(person_id, {"acne": 60.0}, {"acne": 58.0})
    second = band_rows(person_id)  # no bands until the pair is computed
    assert second == []
    noise.compute_band(person_id)
    second_capture = add_capture(person_id, at=T3)
    login(web)

    response = web.get(f"/api/captures/{second_capture}/status")

    assert response.status_code == 200
    assert f'href="/people/{person_id}/baseline"' in response.text
