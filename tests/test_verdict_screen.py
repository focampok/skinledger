"""P11 acceptance tests: the verdict screen, home cards, masks and logging.

All data is SAMPLE or SIMULATED and inserted into a temporary SQLite database.
"""

from __future__ import annotations

import html
import io
import json
import logging
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import SecretStr

from skinledger import config, copy, guards, noise, usage, verdict
from skinledger.db import connect, db_path, init_db
from skinledger.web.app import app

OWNER_TOKEN = "owner-token"
OTHER_TOKEN = "other-token"


@pytest.fixture
def env(tmp_path, monkeypatch):
    settings = config.settings
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    monkeypatch.setattr(settings, "youcam_mock", True)
    monkeypatch.setattr(settings, "invite_code", SecretStr("invite-ok"))
    monkeypatch.setattr(settings, "admin_token", SecretStr("admin-ok"))
    init_db()
    return settings


@pytest.fixture
def web(env):
    with TestClient(app, base_url="https://testserver") as client:
        yield client


# -- helpers -----------------------------------------------------------------


def grey_png() -> bytes:
    buffer = io.BytesIO()
    Image.new("L", (8, 8), color=200).save(buffer, format="PNG")
    return buffer.getvalue()


def login(client: TestClient, token: str = OWNER_TOKEN) -> None:
    client.cookies.set(guards.OWNER_COOKIE, guards.encode_owner_cookie(token))


def at(day: date, hour: int) -> str:
    return f"{day.isoformat()}T{hour:02d}:00:00.000Z"


def _add_mask(
    env,
    conn,
    capture_id: int,
    person_id: int,
    suffix: str,
    aspect: str = "moisture",
) -> str:
    file_name = f"{aspect}_{suffix}.png"
    relative = f"masks/{person_id}/{capture_id}/{file_name}"
    path = env.data_dir / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(grey_png())
    conn.execute(
        "INSERT INTO masks (capture_id, aspect, file_path) VALUES (?, ?, ?)",
        (capture_id, aspect, relative),
    )
    return file_name


def seed_product(
    env,
    *,
    name: str = "Niacinamide serum (SAMPLE)",
    token: str = OWNER_TOKEN,
    started_on: date | None = None,
    targets: tuple[str, ...] = ("moisture",),
    baseline_scores: tuple[float, float] = (50.0, 50.0),
    checkin_score: float | None = 59.0,
    checkin: bool = True,
    data_label: str = "SAMPLE",
    checkin_label: str | None = None,
    checkin_source: str = "camera_kit",
    masks: bool = False,
    ended_on: str | None = None,
) -> tuple[int, int, list[int], int | None]:
    today = usage.guatemala_day()
    start = started_on or (today - timedelta(days=15))
    conn = connect(db_path())
    try:
        person_id = int(
            conn.execute(
                "INSERT INTO persons (display_name, owner_token_hash) VALUES (?, ?)",
                ("Self", guards.owner_token_hash(token)),
            ).lastrowid
        )
        product_id = int(
            conn.execute(
                "INSERT INTO products (person_id, name, category, started_on, "
                "ended_on, target_aspects, data_label) VALUES (?, ?, 'serum', ?, ?, ?, ?)",
                (
                    person_id,
                    name,
                    start.isoformat(),
                    ended_on,
                    json.dumps(list(targets)),
                    data_label,
                ),
            ).lastrowid
        )
        baseline_ids = []
        for index, score in enumerate(baseline_scores):
            capture_id = int(
                conn.execute(
                    "INSERT INTO captures (person_id, owner_token_hash, captured_at, "
                    "data_label, source, status, is_baseline_pair) "
                    "VALUES (?, ?, ?, ?, 'camera_kit', 'success', 1)",
                    (
                        person_id,
                        guards.owner_token_hash(token),
                        at(start, 15 + index),
                        data_label,
                    ),
                ).lastrowid
            )
            baseline_ids.append(capture_id)
            conn.execute(
                "INSERT INTO aspect_scores (capture_id, aspect, raw_score) "
                "VALUES (?, 'moisture', ?)",
                (capture_id, score),
            )
        if masks:
            _add_mask(env, conn, baseline_ids[-1], person_id, "before")
        checkin_id = None
        if checkin:
            checkin_day = start + timedelta(days=14)
            checkin_id = int(
                conn.execute(
                    "INSERT INTO captures (person_id, owner_token_hash, captured_at, "
                    "data_label, source, status, is_baseline_pair) "
                    "VALUES (?, ?, ?, ?, ?, 'success', 0)",
                    (
                        person_id,
                        guards.owner_token_hash(token),
                        at(checkin_day, 15),
                        checkin_label or data_label,
                        checkin_source,
                    ),
                ).lastrowid
            )
            conn.execute(
                "INSERT INTO aspect_scores (capture_id, aspect, raw_score) "
                "VALUES (?, 'moisture', ?)",
                (checkin_id, checkin_score),
            )
            if masks:
                _add_mask(env, conn, checkin_id, person_id, "after")
        conn.commit()
        noise.compute_band(person_id, conn=conn)
    finally:
        conn.close()
    return person_id, product_id, baseline_ids, checkin_id


def verdict_count() -> int:
    conn = connect(db_path())
    try:
        return int(conn.execute("SELECT COUNT(*) FROM verdicts").fetchone()[0])
    finally:
        conn.close()


def add_other_product(person_id: int, *, started_on: date) -> int:
    conn = connect(db_path())
    try:
        product_id = conn.execute(
            "INSERT INTO products (person_id, name, category, started_on, "
            "target_aspects, data_label) VALUES (?, 'Other serum (SAMPLE)', 'serum', "
            "?, '[]', 'SAMPLE')",
            (person_id, started_on.isoformat()),
        ).lastrowid
        conn.commit()
        return int(product_id or 0)
    finally:
        conn.close()


# -- verdict card ------------------------------------------------------------


def test_the_owner_sees_the_verdict_card(env, web):
    person_id, product_id, _, _ = seed_product(env)
    login(web)

    response = web.get(f"/products/{product_id}/verdict")

    assert response.status_code == 200
    assert 'class="verdict-card verdict-keep"' in response.text
    assert 'data-outcome="keep"' in response.text
    assert copy.verdict_outcome_label("keep") in response.text
    assert verdict.KEEP_MESSAGE in response.text
    assert copy.VERDICT_DAY_14 in response.text
    checkin_day = (usage.guatemala_day() - timedelta(days=1)).isoformat()
    assert checkin_day in response.text
    for header in (
        copy.VERDICT_COL_ASPECT,
        copy.VERDICT_COL_BASELINE,
        copy.VERDICT_COL_CHECKIN,
        copy.VERDICT_COL_CHANGE,
        copy.VERDICT_COL_BAND,
        copy.VERDICT_COL_OUTSIDE,
    ):
        assert header in response.text
    assert 'data-target-aspect="moisture"' in response.text
    assert "✓" in response.text
    assert f'/people/{person_id}/capture' in response.text
    assert copy.VERDICT_TAKE_CHECKIN in response.text
    assert "ui_score" not in response.text

    card = response.text.split('class="verdict-card', 1)[1].split("</article>", 1)[0]
    assert copy.DISCLAIMER in card


def test_another_browser_gets_404(env, web):
    _, product_id, _, _ = seed_product(env)
    login(web, OTHER_TOKEN)

    assert web.get(f"/products/{product_id}/verdict").status_code == 404


def test_need_checkin_is_rendered_but_never_persisted(env, web):
    _, product_id, _, _ = seed_product(env, checkin=False)
    login(web)

    response = web.get(f"/products/{product_id}/verdict")

    assert response.status_code == 200
    assert verdict.NEED_CHECKIN_MESSAGE in response.text
    assert copy.verdict_outcome_label("need_checkin") in response.text
    assert verdict_count() == 0


def test_too_early_is_computed_on_read_with_todays_date(env, web):
    start = usage.guatemala_day() - timedelta(days=5)
    _, product_id, _, _ = seed_product(env, started_on=start, checkin=False)
    login(web)

    response = web.get(f"/products/{product_id}/verdict")

    assert response.status_code == 200
    assert verdict.TOO_EARLY_MESSAGE in response.text
    assert copy.verdict_outcome_label("too_early") in response.text


def test_a_simulated_verdict_shows_the_demo_banner(env, web):
    _, product_id, _, _ = seed_product(env, checkin_label="SIMULATED")
    login(web)

    response = web.get(f"/products/{product_id}/verdict")

    assert response.status_code == 200
    assert copy.VERDICT_SIMULATED_BANNER in response.text


def test_a_sample_verdict_shows_the_sample_banner(env, web):
    _, product_id, _, _ = seed_product(env)
    login(web)

    response = web.get(f"/products/{product_id}/verdict")

    assert response.status_code == 200
    assert copy.VERDICT_SAMPLE_BANNER in response.text
    assert copy.VERDICT_SIMULATED_BANNER not in response.text


def test_a_product_without_targets_shows_the_pick_a_target_message(env, web):
    _, product_id, _, _ = seed_product(env, targets=())
    login(web)

    response = web.get(f"/products/{product_id}/verdict")

    assert response.status_code == 200
    assert verdict.NO_TARGETS_MESSAGE in response.text
    assert copy.verdict_outcome_label("no_band") in response.text
    assert copy.VERDICT_TARGETS_TITLE not in response.text


def test_all_unstable_targets_show_the_too_noisy_message(env, web):
    _, product_id, _, _ = seed_product(
        env, baseline_scores=(50.0, 63.0), checkin_score=59.0
    )
    login(web)

    response = web.get(f"/products/{product_id}/verdict")

    assert response.status_code == 200
    assert verdict.ALL_UNSTABLE_MESSAGE in response.text
    assert copy.VERDICT_UNSTABLE_NOT_USED in response.text
    assert 'data-unstable="true"' in response.text


def test_confounding_and_mixed_source_warnings_are_shown(env, web):
    person_id, product_id, _, _ = seed_product(
        env, checkin_source="upload"
    )
    add_other_product(person_id, started_on=usage.guatemala_day() - timedelta(days=10))
    login(web)

    response = web.get(f"/products/{product_id}/verdict")

    assert response.status_code == 200
    page = html.unescape(response.text)
    assert verdict.CONFOUNDED_WARNING in page
    assert verdict.MIXED_SOURCE_WARNING in page


# -- masks -------------------------------------------------------------------


def test_masks_are_not_shown_for_sample_captures(env, web):
    _, product_id, _, _ = seed_product(env, masks=True)
    login(web)

    response = web.get(f"/products/{product_id}/verdict")

    assert response.status_code == 200
    # P16b-7: sample verdicts no longer render an empty masks section.
    assert copy.VERDICT_MASKS_REAL_ONLY not in response.text
    assert copy.VERDICT_MASKS_TITLE not in response.text
    assert 'class="verdict-masks"' not in response.text
    assert "/media/" not in response.text


def test_real_masks_render_and_media_is_no_store_and_not_traversable(env, web):
    _, product_id, baseline_ids, checkin_id = seed_product(
        env, data_label="REAL", masks=True
    )
    login(web)

    page = web.get(f"/products/{product_id}/verdict")

    assert page.status_code == 200
    first_media = page.text.split('src="/media/', 1)[1].split('"', 1)[0]
    capture_id, file_name = first_media.split("/", 1)
    assert int(capture_id) in (*baseline_ids, checkin_id)
    assert copy.VERDICT_MASKS_REAL_ONLY not in page.text
    assert page.text.count('class="verdict-masks"') == 1

    media = web.get(f"/media/{first_media}")
    assert media.status_code == 200
    assert media.headers["cache-control"] == "no-store"

    login(web, OTHER_TOKEN)
    assert web.get(f"/media/{first_media}").status_code == 404
    assert web.get(f"/media/{capture_id}/..%2Fsecret.png").status_code == 404


# -- home and links ----------------------------------------------------------


def test_home_shows_one_card_per_active_product_with_the_next_checkin(env, web):
    seed_product(env, name="Keep serum (SAMPLE)", checkin_score=59.0)
    seed_product(env, name="Steady cream (SAMPLE)", checkin_score=52.0)
    seed_product(
        env,
        name="Ended product (SAMPLE)",
        ended_on=(usage.guatemala_day() - timedelta(days=1)).isoformat(),
    )
    login(web)

    response = web.get("/")

    assert response.status_code == 200
    assert "Keep serum" in response.text
    assert "Steady cream" in response.text
    assert "Ended product" not in response.text
    assert copy.verdict_outcome_label("keep") in response.text
    assert copy.verdict_outcome_label("no_change") in response.text
    assert copy.HOME_NEXT_CHECKIN in response.text
    next_checkin = (usage.guatemala_day() + timedelta(days=13)).isoformat()
    assert next_checkin in response.text


def test_home_does_not_show_products_to_another_browser(env, web):
    seed_product(env, name="Private serum (SAMPLE)")
    login(web, OTHER_TOKEN)

    response = web.get("/")

    assert response.status_code == 200
    assert "Private serum (SAMPLE)" not in response.text
    assert copy.HOME_NO_ACTIVE in response.text


def test_the_products_list_links_to_the_verdict(env, web):
    person_id, product_id, _, _ = seed_product(env)
    login(web)

    response = web.get(f"/people/{person_id}/products")

    assert response.status_code == 200
    assert f'href="/products/{product_id}/verdict"' in response.text


# -- logging -----------------------------------------------------------------


def test_verdict_viewed_logs_only_product_and_outcome(env, web, caplog):
    _, product_id, _, _ = seed_product(env, name="Private serum (SAMPLE)")
    login(web)

    with caplog.at_level(logging.INFO, logger="skinledger.events"):
        assert web.get(f"/products/{product_id}/verdict").status_code == 200

    messages = [
        record.getMessage()
        for record in caplog.records
        if "verdict.viewed" in record.getMessage()
    ]
    assert len(messages) == 1
    assert f"product_id={product_id}" in messages[0]
    assert "outcome=keep" in messages[0]
    assert "person_id" not in messages[0]
    assert "Private serum" not in messages[0]
