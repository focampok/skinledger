"""P09 acceptance tests: product log, validation, HTMX list and timeline order.

All data is SAMPLE and inserted through the routes or straight into SQLite; no images.
"""

from __future__ import annotations

import html
import json
import logging
from datetime import date, timedelta
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from skinledger import config, copy, guards, usage
from skinledger.db import connect, db_path, init_db
from skinledger.web.app import app
from skinledger.web.routes.products import CATEGORIES, MAX_TARGETS

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


def login(client: TestClient, token: str = OWNER_TOKEN) -> None:
    client.cookies.set(guards.OWNER_COOKIE, guards.encode_owner_cookie(token))


def form_data(
    *,
    name: str = "Niacinamide serum (SAMPLE)",
    category: str = "serum",
    started_on: str | None = None,
    ended_on: str = "",
    targets: list[str] | None = None,
) -> list[tuple[str, str]]:
    """Repeated target_aspects keys, exactly like the checkbox form posts them."""
    data = [
        ("name", name),
        ("category", category),
        ("started_on", started_on or usage.guatemala_today()),
        ("ended_on", ended_on),
    ]
    for target in targets if targets is not None else ["oiliness", "pore"]:
        data.append(("target_aspects", target))
    return data


def product_rows(person_id: int) -> list[dict]:
    conn = connect(db_path())
    try:
        rows = conn.execute(
            "SELECT * FROM products WHERE person_id = ? ORDER BY id", (person_id,)
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def product_count() -> int:
    conn = connect(db_path())
    try:
        return int(conn.execute("SELECT COUNT(*) FROM products").fetchone()[0])
    finally:
        conn.close()


def add_unstable_band(person_id: int, aspect: str = "pore", band: float = 17.3) -> None:
    """Two SAMPLE captures plus the stored band row; no scores are needed here."""
    conn = connect(db_path())
    try:
        capture_ids = []
        for at in ("2026-10-28T10:00:00.000Z", "2026-10-28T10:03:00.000Z"):
            capture_ids.append(
                conn.execute(
                    "INSERT INTO captures (person_id, owner_token_hash, captured_at, "
                    "data_label, source, status, is_baseline_pair) "
                    "VALUES (?, ?, ?, 'SAMPLE', 'camera_kit', 'success', 1)",
                    (person_id, guards.owner_token_hash(OWNER_TOKEN), at),
                ).lastrowid
            )
        conn.execute(
            "INSERT INTO noise_bands (person_id, aspect, band, a_capture_id, "
            "b_capture_id, floor_applied, computed_at) VALUES (?, ?, ?, ?, ?, 0, ?)",
            (
                person_id,
                aspect,
                band,
                capture_ids[0],
                capture_ids[1],
                usage.utc_now_iso(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def post_form(
    web: TestClient,
    url: str,
    data: list[tuple[str, str]],
    *,
    headers: dict[str, str] | None = None,
    follow_redirects: bool = True,
):
    """httpx needs an explicit urlencoded body to keep repeated checkbox keys."""
    merged = {"Content-Type": "application/x-www-form-urlencoded"}
    merged.update(headers or {})
    return web.post(
        url,
        content=urlencode(data, doseq=True),
        headers=merged,
        follow_redirects=follow_redirects,
    )


def create_product(web: TestClient, person_id: int, **overrides):
    return post_form(
        web,
        f"/people/{person_id}/products",
        form_data(**overrides),
        follow_redirects=False,
    )


# -- page and creation -------------------------------------------------------


def test_the_products_page_has_the_form_and_15_aspects(env, web):
    person_id = seed_person()
    login(web)

    response = web.get(f"/people/{person_id}/products")

    assert response.status_code == 200
    assert 'placeholder="e.g. Niacinamide serum"' in response.text
    assert "Use a generic name; no brand needed" in response.text
    assert response.text.count('name="target_aspects"') == 15
    for category in CATEGORIES:
        assert f'value="{category}"' in response.text
    assert 'hx-target="#product-panel"' in response.text
    assert copy.DISCLAIMER in response.text


def test_the_form_groups_targets_with_a_counter_and_one_unstable_note(env, web):
    person_id = seed_person()
    add_unstable_band(person_id, aspect="pore")
    login(web)

    page = web.get(f"/people/{person_id}/products")

    assert 'id="target-count"' in page.text
    assert 'data-max-targets="4"' in page.text
    assert "0 of 4 selected" in page.text
    assert page.text.count('class="product-group"') == 4
    assert page.text.count('name="target_aspects"') == 15
    assert html.unescape(page.text).count(copy.PRODUCT_UNSTABLE_HINT) == 1


def test_the_product_list_comes_before_the_add_form_and_has_cards(env, web):
    person_id = seed_person()
    login(web)
    assert create_product(web, person_id).status_code == 303

    page = web.get(f"/people/{person_id}/products").text

    assert page.index('id="product-panel"') < page.index('class="product-add"')
    assert 'class="product-cards"' in page
    assert 'class="product-card"' in page
    assert 'class="product-table-wrap"' in page
    assert 'role="button">Verdict</a>' in page


def test_creating_a_product_stores_real_data_and_shows_checkin_dates(env, web):
    person_id = seed_person()
    login(web)

    response = create_product(web, person_id, started_on="2026-10-28")

    assert response.status_code == 303
    assert response.headers["location"].startswith(
        f"/people/{person_id}/products?created="
    )
    rows = product_rows(person_id)
    assert len(rows) == 1
    assert rows[0]["data_label"] == "REAL"
    assert rows[0]["category"] == "serum"
    assert rows[0]["ended_on"] is None
    assert json.loads(rows[0]["target_aspects"]) == ["oiliness", "pore"]

    page = web.get(response.headers["location"])
    assert page.status_code == 200
    assert (
        "Check-ins: day 14 (between days 12–20) on 2026-11-11 and "
        "day 28 (26–35) on 2026-11-25." in page.text
    )


def test_a_blank_name_is_rejected(env, web):
    person_id = seed_person()
    login(web)

    response = create_product(web, person_id, name="")

    assert response.status_code == 400
    assert copy.PRODUCT_NAME_REQUIRED in response.text
    assert product_count() == 0


def test_an_unknown_category_is_rejected(env, web):
    person_id = seed_person()
    login(web)

    response = create_product(web, person_id, category="snake oil")

    assert response.status_code == 400
    assert copy.PRODUCT_CATEGORY_INVALID in response.text
    assert product_count() == 0


# -- target validation -------------------------------------------------------


def test_a_product_needs_at_least_one_target(env, web):
    person_id = seed_person()
    login(web)

    response = create_product(web, person_id, targets=[])

    assert response.status_code == 400
    assert "Pick 1 to 4 target aspects." in response.text
    assert product_count() == 0


def test_more_than_four_targets_is_rejected(env, web):
    person_id = seed_person()
    login(web)
    targets = ["acne", "moisture", "pore", "texture", "redness"]
    assert len(targets) > MAX_TARGETS

    response = create_product(web, person_id, targets=targets)

    assert response.status_code == 400
    assert copy.PRODUCT_TOO_MANY_TARGETS in response.text
    assert product_count() == 0


@pytest.mark.parametrize("target", ["skin_type", "not_an_aspect"])
def test_an_unknown_target_aspect_is_rejected(env, web, target):
    person_id = seed_person()
    login(web)

    response = create_product(web, person_id, targets=[target])

    assert response.status_code == 400
    assert copy.PRODUCT_UNKNOWN_TARGET in response.text
    assert product_count() == 0


def test_an_end_date_before_the_start_is_rejected(env, web):
    person_id = seed_person()
    login(web)

    response = create_product(
        web, person_id, started_on="2026-10-28", ended_on="2026-10-27"
    )

    assert response.status_code == 400
    assert "End date can't be before the start date." in html.unescape(response.text)
    assert product_count() == 0


# -- list, end action and days elapsed ---------------------------------------


def test_the_list_shows_days_elapsed(env, web):
    person_id = seed_person()
    login(web)
    started = (date.fromisoformat(usage.guatemala_today()) - timedelta(days=3)).isoformat()
    assert create_product(web, person_id, started_on=started).status_code == 303

    page = web.get(f"/people/{person_id}/products")

    assert "3 days" in page.text


def test_the_end_action_sets_ended_on_today(env, web):
    person_id = seed_person()
    login(web)
    assert create_product(web, person_id).status_code == 303
    product_id = product_rows(person_id)[0]["id"]

    response = web.post(
        f"/people/{person_id}/products/{product_id}/end", follow_redirects=False
    )

    assert response.status_code == 303
    row = product_rows(person_id)[0]
    assert row["ended_on"] == usage.guatemala_today()

    page = web.get(f"/people/{person_id}/products")
    assert 'data-active="false"' in page.text
    assert "Ended" in page.text


def test_an_unstable_aspect_shows_the_hint_and_can_still_be_saved(env, web):
    person_id = seed_person()
    add_unstable_band(person_id, aspect="pore")
    login(web)

    page = web.get(f"/people/{person_id}/products")
    assert copy.PRODUCT_UNSTABLE_HINT in html.unescape(page.text)

    response = create_product(web, person_id, targets=["pore"])

    assert response.status_code == 303
    assert json.loads(product_rows(person_id)[0]["target_aspects"]) == ["pore"]


# -- HTMX --------------------------------------------------------------------


def test_htmx_create_returns_only_the_list_panel(env, web):
    person_id = seed_person()
    login(web)

    response = post_form(
        web,
        f"/people/{person_id}/products",
        form_data(),
        headers={"HX-Request": "true"},
    )

    assert response.status_code == 200
    assert 'id="product-panel"' in response.text
    assert "<html" not in response.text.lower()
    assert "Niacinamide serum (SAMPLE)" in response.text
    assert "Check-ins: day 14 (between days 12–20)" in response.text


# -- ownership and cascade ---------------------------------------------------


def test_another_browser_gets_404_on_the_page_and_actions(env, web):
    person_id = seed_person()
    login(web)
    assert create_product(web, person_id).status_code == 303
    product_id = product_rows(person_id)[0]["id"]

    login(web, OTHER_TOKEN)

    assert web.get(f"/people/{person_id}/products").status_code == 404
    assert create_product(web, person_id).status_code == 404
    assert web.post(
        f"/people/{person_id}/products/{product_id}/end"
    ).status_code == 404
    assert len(product_rows(person_id)) == 1


def test_deleting_the_person_deletes_their_products(env, web):
    person_id = seed_person(name="Self")
    login(web)
    assert create_product(web, person_id).status_code == 303
    assert product_count() == 1

    response = web.post(f"/people/{person_id}/delete", data={"confirm_name": "Self"})

    assert response.status_code == 200
    assert product_count() == 0
    assert product_rows(person_id) == []


# -- timeline integration ----------------------------------------------------


def test_the_timeline_puts_product_targets_first_and_exposes_the_start_date(env, web):
    person_id = seed_person()
    login(web)
    assert create_product(
        web, person_id, started_on="2026-10-20", targets=["oiliness", "pore"]
    ).status_code == 303

    series = web.get(f"/api/people/{person_id}/series").json()

    assert series["products"][0]["started_on"] == "2026-10-20"
    assert series["products"][0]["target_aspects"] == ["oiliness", "pore"]
    assert [aspect["aspect"] for aspect in series["aspects"][:2]] == [
        "oiliness",
        "pore",
    ]
    assert [aspect["group"] for aspect in series["aspects"][:2]] == [
        "target",
        "target",
    ]


# -- logging -----------------------------------------------------------------


def test_product_events_log_only_person_and_product_ids(env, web, caplog):
    person_id = seed_person()
    login(web)

    with caplog.at_level(logging.INFO, logger="skinledger.events"):
        assert create_product(web, person_id).status_code == 303
        product_id = product_rows(person_id)[0]["id"]
        assert web.post(
            f"/people/{person_id}/products/{product_id}/end",
            follow_redirects=False,
        ).status_code == 303

    messages = [record.getMessage() for record in caplog.records]
    created = [message for message in messages if "product.created" in message]
    ended = [message for message in messages if "product.ended" in message]
    assert len(created) == 1
    assert len(ended) == 1
    for message in (created[0], ended[0]):
        assert f"person_id={person_id}" in message
        assert f"product_id={product_id}" in message
        assert "Niacinamide serum" not in message
