"""P12 acceptance tests: fixed AM/PM routine, shopping list and the routine page.

All data is SAMPLE/SIMULATED and inserted into SQLite or passed as plain dicts;
no images, no ui_score and no brands.
"""

from __future__ import annotations

import logging
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from skinledger import config, copy, guards, noise, shopping, usage
from skinledger import routine as routine_engine
from skinledger.aspects import NUMERIC_ASPECTS
from skinledger.db import connect, db_path, init_db
from skinledger.web.app import app

OWNER_TOKEN = "owner-token"
OTHER_TOKEN = "other-token"

BANNED_WORDS = ("diagnos", "treat", "cure", "disease", "prescription", "medication")
BRANDS = (
    "cerave",
    "cetaphil",
    "neutrogena",
    "la roche",
    "the ordinary",
    "paula's choice",
    "olay",
    "nivea",
    "clinique",
)


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


# -- pure helpers ------------------------------------------------------------


def sample_scores(value: float = 60.0, **overrides: float) -> dict[str, float]:
    scores = {aspect: value for aspect in NUMERIC_ASPECTS}
    scores.update(overrides)
    return scores


def sample_capture(scores: dict[str, float], *, data_label: str = "SAMPLE") -> dict:
    return {
        "id": 1,
        "captured_at": "2026-10-24T15:00:00.000Z",
        "data_label": data_label,
        "scores": scores,
    }


def stable_bands() -> dict[str, dict[str, object]]:
    return {
        aspect: {
            "band": 3.0,
            "floor_applied": True,
            "unstable": noise.is_unstable(3.0),
        }
        for aspect in NUMERIC_ASPECTS
    }


def unstable_band() -> dict[str, object]:
    return {
        "band": 13.0,
        "floor_applied": False,
        "unstable": noise.is_unstable(13.0),
    }


def names(items) -> list[str]:
    return [item.name for item in items]


# -- the three acceptance scenarios -----------------------------------------


def test_oiliness_pore_texture_gets_niacinamide_gel_and_aha():
    routine = routine_engine.build_routine(
        sample_capture(sample_scores(80, oiliness=20, pore=25, texture=30)),
        stable_bands(),
    )

    assert [item.aspect for item in routine.lowest] == ["oiliness", "pore", "texture"]
    assert "Niacinamide serum" in names(routine.am)
    assert "Lightweight gel moisturizer" in names(routine.am)
    assert "Niacinamide serum" in names(routine.pm)
    assert "Gentle exfoliant (AHA/PHA)" in names(routine.pm)
    assert "Gentle exfoliant (AHA/PHA)" not in names(routine.am)


def test_wrinkle_acne_moisture_never_puts_retinol_and_bha_on_the_same_night():
    routine = routine_engine.build_routine(
        sample_capture(sample_scores(80, wrinkle=20, acne=25, moisture=30)),
        stable_bands(),
    )

    assert "Retinol serum" in names(routine.pm)
    cleanser = next(item for item in routine.pm if item.category == "cleanser")
    assert "Salicylic acid (BHA) cleanser" in cleanser.alternatives
    assert "Salicylic acid (BHA) cleanser" in cleanser.display
    retinol_nights = [day for day in routine.week if "Retinol serum" in day.pm]
    bha_nights = [
        day for day in routine.week if "Salicylic acid (BHA) cleanser" in day.pm
    ]
    assert retinol_nights and bha_nights
    for day in routine.week:
        assert not ("Retinol serum" in day.pm and "Salicylic acid (BHA) cleanser" in day.pm)


def test_redness_among_the_lowest_limits_exfoliating_to_two_nights():
    routine = routine_engine.build_routine(
        sample_capture(sample_scores(80, redness=20, texture=25, moisture=30)),
        stable_bands(),
    )

    exfoliant_nights = [
        day for day in routine.week if "Gentle exfoliant (AHA/PHA)" in day.pm
    ]
    assert 1 <= len(exfoliant_nights) <= 2


# -- stable-only selection and notes ----------------------------------------


def test_unstable_aspects_are_excluded_from_the_lowest_three():
    bands = stable_bands()
    bands["pore"] = unstable_band()
    routine = routine_engine.build_routine(
        sample_capture(sample_scores(80, pore=10, moisture=20, acne=30, texture=40)),
        bands,
    )

    assert [item.aspect for item in routine.lowest] == ["moisture", "acne", "texture"]
    assert "pore" not in [item.aspect for item in routine.lowest]
    assert routine.unstable_excluded is True
    assert copy.ROUTINE_UNSTABLE_EXCLUDED in routine.notes


def test_fewer_than_three_stable_aspects_uses_what_is_available_and_says_so():
    bands = stable_bands()
    for aspect in NUMERIC_ASPECTS:
        if aspect not in ("moisture", "acne"):
            bands[aspect] = unstable_band()
    routine = routine_engine.build_routine(
        sample_capture(sample_scores(80, moisture=20, acne=30)),
        bands,
    )

    assert [item.aspect for item in routine.lowest] == ["moisture", "acne"]
    assert copy.ROUTINE_FEW_STABLE in routine.notes


def test_no_bands_uses_all_aspects_and_shows_the_one_capture_note():
    routine = routine_engine.build_routine(
        sample_capture(sample_scores(80, moisture=20, acne=30, texture=40)),
        {},
    )

    assert routine.has_bands is False
    assert [item.aspect for item in routine.lowest] == ["moisture", "acne", "texture"]
    assert copy.ROUTINE_ONE_CAPTURE in routine.notes


def test_acne_as_the_lowest_sets_the_disclaimer_flag():
    routine = routine_engine.build_routine(
        sample_capture(sample_scores(80, acne=10, moisture=40, texture=50)),
        stable_bands(),
    )

    assert routine.acne_lowest is True


# -- shopping list -----------------------------------------------------------


def test_no_slot_has_two_items_of_the_same_category():
    scenarios = (
        sample_scores(80, oiliness=20, moisture=25, redness=30),
        sample_scores(80, wrinkle=20, acne=25, texture=30),
        sample_scores(80, redness=20, texture=25, dark_circle_v2=30),
    )
    for scores in scenarios:
        routine = routine_engine.build_routine(sample_capture(scores), stable_bands())
        for slot in (routine.am, routine.pm):
            categories = [item.category for item in slot]
            assert len(categories) == len(set(categories))


def test_spf_is_the_last_am_item():
    routine = routine_engine.build_routine(
        sample_capture(sample_scores(80, wrinkle=20, acne=25, moisture=30)),
        stable_bands(),
    )

    assert routine.am[-1].name == copy.ROUTINE_ITEM_SPF
    assert routine.am[-1].category == "sunscreen"


def test_advice_is_a_note_and_never_a_shopping_item():
    routine = routine_engine.build_routine(
        sample_capture(
            sample_scores(80, redness=20, texture=25, dark_circle_v2=30)
        ),
        stable_bands(),
    )
    items = shopping.build_shopping_list([*routine.am, *routine.pm], [])

    assert copy.ROUTINE_ITEM_AVOID_TONERS in routine.am_notes
    assert copy.ROUTINE_ITEM_AVOID_TONERS in routine.pm_notes
    assert copy.ROUTINE_EYE_NOTE in routine.am_notes
    assert copy.ROUTINE_ITEM_AVOID_TONERS not in names(items)
    assert copy.ROUTINE_EYE_NOTE not in names(items)


def test_the_shopping_list_drops_categories_covered_by_active_products():
    routine = routine_engine.build_routine(
        sample_capture(sample_scores(80, oiliness=20, pore=25, texture=30)),
        stable_bands(),
    )

    items = shopping.build_shopping_list(
        [*routine.am, *routine.pm], ["serum", "exfoliant"]
    )

    assert "Niacinamide serum" not in names(items)
    assert "Gentle exfoliant (AHA/PHA)" not in names(items)
    assert "Lightweight gel moisturizer" in names(items)


def test_routine_and_shopping_outputs_have_no_banned_word_or_brand():
    routine = routine_engine.build_routine(
        sample_capture(
            sample_scores(
                80,
                oiliness=20,
                pore=25,
                texture=30,
                redness=35,
                wrinkle=40,
                acne=45,
            )
        ),
        stable_bands(),
    )
    items = shopping.build_shopping_list([*routine.am, *routine.pm], [])
    texts = (
        [item.display for item in routine.am]
        + [item.display for item in routine.pm]
        + [alt for item in (*routine.am, *routine.pm) for alt in item.alternatives]
        + [item.name for item in items]
        + routine.notes
        + routine.am_notes
        + routine.pm_notes
        + [copy.ROUTINE_FOOTER]
    )

    for text in texts:
        lowered = text.lower()
        for word in (*BANNED_WORDS, *BRANDS):
            assert word not in lowered, f"{word!r} in {text!r}"


# -- route helpers -----------------------------------------------------------


def login(client: TestClient, token: str = OWNER_TOKEN) -> None:
    client.cookies.set(guards.OWNER_COOKIE, guards.encode_owner_cookie(token))


def _insert_capture(
    conn,
    person_id: int,
    token: str,
    captured_at: str,
    scores: dict[str, float],
    data_label: str,
    *,
    is_baseline_pair: int,
) -> int:
    capture_id = int(
        conn.execute(
            "INSERT INTO captures (person_id, owner_token_hash, captured_at, data_label, "
            "source, status, is_baseline_pair) "
            "VALUES (?, ?, ?, ?, 'camera_kit', 'success', ?)",
            (
                person_id,
                guards.owner_token_hash(token),
                captured_at,
                data_label,
                is_baseline_pair,
            ),
        ).lastrowid
    )
    for aspect, score in scores.items():
        conn.execute(
            "INSERT INTO aspect_scores (capture_id, aspect, raw_score) VALUES (?, ?, ?)",
            (capture_id, aspect, score),
        )
    return capture_id


def seed_routine_person(
    env,
    *,
    token: str = OWNER_TOKEN,
    latest_scores: dict[str, float] | None = None,
    data_label: str = "SAMPLE",
    banded: bool = True,
    unstable_pore: bool = False,
    with_product: bool = False,
) -> tuple[int, str]:
    start = usage.guatemala_day() - timedelta(days=15)
    conn = connect(db_path())
    try:
        person_id = int(
            conn.execute(
                "INSERT INTO persons (display_name, owner_token_hash) VALUES (?, ?)",
                ("Self", guards.owner_token_hash(token)),
            ).lastrowid
        )
        for index, hour in enumerate((15, 16)):
            scores = sample_scores(50.0)
            if unstable_pore and index == 1:
                scores["pore"] = 63.0
            _insert_capture(
                conn,
                person_id,
                token,
                f"{start.isoformat()}T{hour:02d}:00:00.000Z",
                scores,
                data_label,
                is_baseline_pair=1,
            )
        latest = latest_scores or sample_scores(
            80.0, oiliness=20.0, pore=25.0, texture=30.0
        )
        _insert_capture(
            conn,
            person_id,
            token,
            f"{(start + timedelta(days=14)).isoformat()}T15:00:00.000Z",
            latest,
            data_label,
            is_baseline_pair=0,
        )
        if with_product:
            conn.execute(
                "INSERT INTO products (person_id, name, category, started_on, "
                "target_aspects, data_label) VALUES (?, 'Niacinamide serum (SAMPLE)', "
                "'serum', ?, '[\"moisture\"]', 'SAMPLE')",
                (person_id, start.isoformat()),
            )
        conn.commit()
        if banded:
            noise.compute_band(person_id, conn=conn)
    finally:
        conn.close()
    return person_id, start.isoformat()


# -- route -------------------------------------------------------------------


def test_the_owner_sees_the_routine_page(env, web):
    person_id, _ = seed_routine_person(env)
    login(web)

    response = web.get(f"/people/{person_id}/routine")

    assert response.status_code == 200
    assert copy.ROUTINE_TITLE in response.text
    assert copy.ROUTINE_LOWEST_TITLE in response.text
    assert copy.ROUTINE_AM_TITLE in response.text
    assert copy.ROUTINE_PM_TITLE in response.text
    assert copy.ROUTINE_WEEK_TITLE in response.text
    assert copy.ROUTINE_SHOPPING_TITLE in response.text
    assert "Niacinamide serum" in response.text
    assert "Gentle exfoliant (AHA/PHA)" in response.text
    assert 'data-aspect="oiliness"' in response.text
    assert 'data-aspect="pore"' in response.text
    assert 'data-aspect="texture"' in response.text
    assert f"{copy.ROUTINE_DATA_PREFIX}: SAMPLE" in response.text
    assert 'id="shopping-list"' in response.text
    assert 'id="copy-list"' in response.text
    assert 'src="/static/routine.js"' in response.text
    assert copy.ROUTINE_FOOTER in response.text
    assert "ui_score" not in response.text


def test_another_browser_gets_404(env, web):
    person_id, _ = seed_routine_person(env)
    login(web, OTHER_TOKEN)

    assert web.get(f"/people/{person_id}/routine").status_code == 404


def test_unstable_aspects_are_excluded_on_the_page(env, web):
    person_id, _ = seed_routine_person(env, unstable_pore=True)
    login(web)

    response = web.get(f"/people/{person_id}/routine")

    assert response.status_code == 200
    assert 'data-aspect="pore"' not in response.text
    assert copy.ROUTINE_UNSTABLE_EXCLUDED in response.text


def test_fewer_than_three_stable_aspects_says_so_on_the_page(env, web):
    person_id, _ = seed_routine_person(env)
    conn = connect(db_path())
    try:
        conn.execute(
            "UPDATE noise_bands SET band = 13.0 WHERE person_id = ? "
            "AND aspect NOT IN ('oiliness', 'texture')",
            (person_id,),
        )
        conn.commit()
    finally:
        conn.close()
    login(web)

    response = web.get(f"/people/{person_id}/routine")

    assert response.status_code == 200
    assert copy.ROUTINE_FEW_STABLE in response.text
    assert 'data-aspect="oiliness"' in response.text
    assert 'data-aspect="texture"' in response.text
    assert 'data-aspect="pore"' not in response.text


def test_no_bands_shows_the_one_capture_note(env, web):
    person_id, _ = seed_routine_person(env, banded=False)
    login(web)

    response = web.get(f"/people/{person_id}/routine")

    assert response.status_code == 200
    assert copy.ROUTINE_ONE_CAPTURE in response.text


def test_a_non_real_capture_shows_its_label(env, web):
    person_id, _ = seed_routine_person(env, data_label="SIMULATED")
    login(web)

    response = web.get(f"/people/{person_id}/routine")

    assert response.status_code == 200
    assert f"{copy.ROUTINE_DATA_PREFIX}: SIMULATED" in response.text


def test_a_keep_product_is_marked_keep_using(env, web):
    person_id, _ = seed_routine_person(env, with_product=True)
    login(web)

    response = web.get(f"/people/{person_id}/routine")

    assert response.status_code == 200
    assert copy.ROUTINE_KEEP_USING in response.text
    assert "Niacinamide serum (SAMPLE)" in response.text


def test_acne_as_the_lowest_shows_the_disclaimer_inside_the_card(env, web):
    person_id, _ = seed_routine_person(
        env, latest_scores=sample_scores(80, acne=10, moisture=40, texture=50)
    )
    login(web)

    response = web.get(f"/people/{person_id}/routine")

    assert response.status_code == 200
    assert 'class="routine-acne-disclaimer"' in response.text
    block = response.text.split('class="routine-acne-disclaimer"', 1)[1].split(
        "</p>", 1
    )[0]
    assert copy.DISCLAIMER in block


def test_the_shopping_list_drops_an_active_exfoliant_category(env, web):
    person_id, start = seed_routine_person(env)
    conn = connect(db_path())
    try:
        conn.execute(
            "INSERT INTO products (person_id, name, category, started_on, "
            "target_aspects, data_label) VALUES (?, 'Body exfoliant (SAMPLE)', "
            "'exfoliant', ?, '[]', 'SAMPLE')",
            (person_id, start),
        )
        conn.commit()
    finally:
        conn.close()
    login(web)

    response = web.get(f"/people/{person_id}/routine")

    assert response.status_code == 200
    shopping_block = response.text.split('id="shopping-list"', 1)[1].split(
        "</ul>", 1
    )[0]
    assert "Gentle exfoliant (AHA/PHA)" not in shopping_block


def test_the_routine_is_linked_from_people_and_the_timeline(env, web):
    person_id, _ = seed_routine_person(env)
    login(web)
    link = f'href="/people/{person_id}/routine"'

    assert link in web.get("/people").text
    assert link in web.get(f"/people/{person_id}/timeline").text


def test_routine_viewed_logs_person_and_aspects_only(env, web, caplog):
    person_id, _ = seed_routine_person(env)
    login(web)

    with caplog.at_level(logging.INFO, logger="skinledger.events"):
        assert web.get(f"/people/{person_id}/routine").status_code == 200

    messages = [
        record.getMessage()
        for record in caplog.records
        if "routine.viewed" in record.getMessage()
    ]
    assert len(messages) == 1
    assert f"person_id={person_id}" in messages[0]
    assert "aspects=oiliness,pore,texture" in messages[0]
    assert "20.0" not in messages[0]
    assert "Self" not in messages[0]
