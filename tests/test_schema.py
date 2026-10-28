"""P02 acceptance tests: schema, cascades, forbidden columns, pragmas and aspects."""

import sqlite3
from dataclasses import fields

import pytest

from skinledger import models
from skinledger.aspects import ASPECT_LABELS, NUMERIC_ASPECTS, SD_ACTIONS
from skinledger.db import connect, init_db

SD_ACTIONS_FROM_AGENTS = {
    "wrinkle",
    "droopy_upper_eyelid",
    "droopy_lower_eyelid",
    "firmness",
    "acne",
    "moisture",
    "eye_bag",
    "dark_circle_v2",
    "age_spot",
    "radiance",
    "redness",
    "oiliness",
    "pore",
    "texture",
    "tear_trough",
    "skin_type",
}

MODEL_TABLES = {
    models.Person: "persons",
    models.Consent: "consents",
    models.Capture: "captures",
    models.AspectScore: "aspect_scores",
    models.Mask: "masks",
    models.NoiseBand: "noise_bands",
    models.Product: "products",
    models.Verdict: "verdicts",
    models.ApiUsage: "api_usage",
}


@pytest.fixture
def conn(tmp_path):
    path = init_db(tmp_path / "skinledger.sqlite")
    connection = connect(path)
    try:
        yield connection
    finally:
        connection.close()


def _insert_person(conn, name="Self"):
    cursor = conn.execute(
        "INSERT INTO persons (display_name, owner_token_hash) VALUES (?, ?)",
        (name, "browser-hash"),
    )
    return cursor.lastrowid


def _insert_capture(conn, person_id, **overrides):
    values = {
        "person_id": person_id,
        "owner_token_hash": "browser-hash",
        "captured_at": "2026-10-28T18:00:00Z",
        "data_label": "REAL",
        "source": "upload",
        "status": "success",
    }
    values.update(overrides)
    columns = ", ".join(values)
    placeholders = ", ".join("?" for _ in values)
    cursor = conn.execute(
        f"INSERT INTO captures ({columns}) VALUES ({placeholders})",
        tuple(values.values()),
    )
    return cursor.lastrowid


def _table_names(conn):
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    )
    return [row["name"] for row in rows]


def _columns(conn, table):
    return [row["name"] for row in conn.execute(f"PRAGMA table_info({table})")]


def test_init_db_is_idempotent(tmp_path):
    path = tmp_path / "nested" / "skinledger.sqlite"

    init_db(path)
    init_db(path)

    conn = connect(path)
    try:
        tables = set(_table_names(conn))
    finally:
        conn.close()
    assert tables == {
        "persons",
        "consents",
        "captures",
        "aspect_scores",
        "masks",
        "noise_bands",
        "products",
        "verdicts",
        "api_usage",
    }


def test_connection_enables_wal_and_foreign_keys(conn):
    assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_delete_person_cascades_and_api_usage_survives(conn):
    person_id = _insert_person(conn)
    conn.execute(
        "INSERT INTO consents (person_id, consent_version, adult_confirmed, accepted_at) "
        "VALUES (?, ?, ?, ?)",
        (person_id, "v1", 1, "2026-10-28T18:00:00Z"),
    )
    capture_a = _insert_capture(conn, person_id)
    capture_b = _insert_capture(conn, person_id, captured_at="2026-10-28T18:05:00Z")
    conn.execute(
        "INSERT INTO aspect_scores (capture_id, aspect, raw_score) VALUES (?, ?, ?)",
        (capture_a, "moisture", 61.5),
    )
    conn.execute(
        "INSERT INTO aspect_scores (capture_id, aspect, value_text) VALUES (?, ?, ?)",
        (capture_a, "skin_type", "combination"),
    )
    conn.execute(
        "INSERT INTO masks (capture_id, aspect, file_path) VALUES (?, ?, ?)",
        (capture_a, "moisture", "masks/1/1/moisture.png"),
    )
    conn.execute(
        "INSERT INTO noise_bands "
        "(person_id, aspect, band, a_capture_id, b_capture_id, floor_applied, computed_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (person_id, "moisture", 3.0, capture_a, capture_b, 1, "2026-10-28T18:10:00Z"),
    )
    product_id = conn.execute(
        "INSERT INTO products "
        "(person_id, name, category, started_on, target_aspects, data_label) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (person_id, "Niacinamide serum (SAMPLE)", "serum", "2026-10-28", '["moisture"]', "SAMPLE"),
    ).lastrowid
    conn.execute(
        "INSERT INTO verdicts "
        "(product_id, check_window, outcome, payload_json, computed_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (product_id, "d14", "keep", "{}", "2026-11-11T18:00:00Z"),
    )
    conn.execute(
        "INSERT INTO api_usage (capture_id, owner_token_hash, day, units, mode) "
        "VALUES (?, ?, ?, ?, ?)",
        (capture_a, "browser-hash", "2026-10-28", 16, "real"),
    )
    conn.commit()

    conn.execute("DELETE FROM persons WHERE id = ?", (person_id,))
    conn.commit()

    for table in (
        "consents",
        "captures",
        "aspect_scores",
        "masks",
        "noise_bands",
        "products",
        "verdicts",
    ):
        count = conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        assert count == 0, table

    usage = conn.execute("SELECT capture_id, units FROM api_usage").fetchone()
    assert usage["capture_id"] is None
    assert usage["units"] == 16


@pytest.mark.parametrize(
    ("column", "value"),
    [("data_label", "FAKE"), ("source", "dev_upload")],
)
def test_captures_reject_invalid_labels(conn, column, value):
    person_id = _insert_person(conn)
    with pytest.raises(sqlite3.IntegrityError):
        _insert_capture(conn, person_id, **{column: value})


def test_verdicts_reject_an_unknown_outcome(conn):
    person_id = _insert_person(conn)
    product_id = conn.execute(
        "INSERT INTO products "
        "(person_id, name, category, started_on, target_aspects, data_label) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (person_id, "Ceramide moisturizer (SAMPLE)", "moisturizer", "2026-10-28", "[]", "SAMPLE"),
    ).lastrowid

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO verdicts "
            "(product_id, check_window, outcome, payload_json, computed_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (product_id, "d14", "maybe", "{}", "2026-11-11T18:00:00Z"),
        )


def test_captures_has_no_photo_or_image_column(conn):
    columns = _columns(conn, "captures")
    assert not [name for name in columns if "photo" in name.lower() or "image" in name.lower()]


def test_aspect_scores_has_no_ui_score(conn):
    assert "ui_score" not in _columns(conn, "aspect_scores")


def test_no_table_stores_a_photo_or_ui_score(conn):
    for table in _table_names(conn):
        for column in _columns(conn, table):
            lowered = column.lower()
            assert "photo" not in lowered, f"{table}.{column}"
            assert "image" not in lowered, f"{table}.{column}"
            assert "ui_score" not in lowered, f"{table}.{column}"


def test_youcam_ids_are_opaque_text(conn):
    types = {row["name"]: row["type"] for row in conn.execute("PRAGMA table_info(captures)")}
    assert types["file_id"] == "TEXT"
    assert types["task_id"] == "TEXT"


def test_dataclasses_match_table_columns(conn):
    for model, table in MODEL_TABLES.items():
        assert {field.name for field in fields(model)} == set(_columns(conn, table)), table


def test_sd_actions_are_the_16_verified_aspects():
    assert len(SD_ACTIONS) == 16
    assert len(set(SD_ACTIONS)) == 16
    assert not any(action.startswith("hd_") for action in SD_ACTIONS)
    assert set(SD_ACTIONS) == SD_ACTIONS_FROM_AGENTS


def test_numeric_aspects_exclude_skin_type():
    assert len(NUMERIC_ASPECTS) == 15
    assert "skin_type" not in NUMERIC_ASPECTS
    assert set(SD_ACTIONS) == set(NUMERIC_ASPECTS) | {"skin_type"}


def test_every_aspect_has_an_english_label():
    assert set(ASPECT_LABELS) == set(SD_ACTIONS)
    assert all(label.strip() for label in ASPECT_LABELS.values())
