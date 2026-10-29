"""P13 acceptance tests: the copy and disclaimer audit, with file:line findings."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from skinledger import (
    config,
    copy,
    copy_audit,
    guards,
    noise,
    routine,
    shopping,
    usage,
    verdict,
)
from skinledger.aspects import NUMERIC_ASPECTS
from skinledger.db import connect, db_path, init_db
from skinledger.web.app import app

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "src/skinledger/web/templates"
STATIC = ROOT / "src/skinledger/web/static"

OWNER_TOKEN = "owner-token"

BANNED_BRANDS = (
    "cerave",
    "cetaphil",
    "neutrogena",
    "la roche",
    "the ordinary",
    "paula's choice",
    "olay",
    "nivea",
    "clinique",
    "estee lauder",
    "l'oreal",
    "kiehl",
    "avene",
    "eucerin",
    "bioderma",
    "biore",
    "garnier",
    "cosrx",
    "innisfree",
    "laneige",
    "drunk elephant",
    "glossier",
    "fenty",
    "sephora",
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


def login(client: TestClient) -> None:
    client.cookies.set(guards.OWNER_COOKIE, guards.encode_owner_cookie(OWNER_TOKEN))


def _insert_capture(
    conn,
    person_id: int,
    captured_at: str,
    scores: dict[str, float],
    *,
    baseline_pair: int = 0,
) -> int:
    capture_id = int(
        conn.execute(
            "INSERT INTO captures (person_id, owner_token_hash, captured_at, data_label, "
            "source, status, is_baseline_pair) "
            "VALUES (?, ?, ?, 'SAMPLE', 'camera_kit', 'success', ?)",
            (
                person_id,
                guards.owner_token_hash(OWNER_TOKEN),
                captured_at,
                baseline_pair,
            ),
        ).lastrowid
    )
    for aspect, score in scores.items():
        conn.execute(
            "INSERT INTO aspect_scores (capture_id, aspect, raw_score) VALUES (?, ?, ?)",
            (capture_id, aspect, score),
        )
    return capture_id


def seed_audit_data(env) -> tuple[int, int]:
    start = usage.guatemala_day() - timedelta(days=15)
    conn = connect(db_path())
    try:
        person_id = int(
            conn.execute(
                "INSERT INTO persons (display_name, owner_token_hash) VALUES (?, ?)",
                ("Self", guards.owner_token_hash(OWNER_TOKEN)),
            ).lastrowid
        )
        conn.execute(
            "INSERT INTO consents (person_id, consent_version, adult_confirmed, accepted_at) "
            "VALUES (?, ?, 1, ?)",
            (person_id, copy.CONSENT_VERSION, usage.utc_now_iso()),
        )
        baseline = {aspect: 50.0 for aspect in NUMERIC_ASPECTS}
        for hour in (15, 16):
            _insert_capture(
                conn,
                person_id,
                f"{start.isoformat()}T{hour:02d}:00:00.000Z",
                baseline,
                baseline_pair=1,
            )
        latest = {aspect: 60.0 for aspect in NUMERIC_ASPECTS}
        latest["moisture"] = 59.0
        _insert_capture(
            conn,
            person_id,
            f"{(start + timedelta(days=14)).isoformat()}T15:00:00.000Z",
            latest,
        )
        product_id = int(
            conn.execute(
                "INSERT INTO products (person_id, name, category, started_on, "
                "target_aspects, data_label) VALUES (?, 'Niacinamide serum (SAMPLE)', "
                "'serum', ?, '[\"moisture\"]', 'SAMPLE')",
                (person_id, start.isoformat()),
            ).lastrowid
        )
        conn.commit()
        noise.compute_band(person_id, conn=conn)
    finally:
        conn.close()
    return person_id, product_id


# -- static scan -------------------------------------------------------------


def test_repo_copy_has_no_banned_words_brands_or_disallowed_youcam():
    findings = copy_audit.audit_repo(ROOT, brands=BANNED_BRANDS)

    assert not findings, copy_audit.format_findings(findings)


def test_writing_treatment_fails_with_file_line(tmp_path):
    bad = tmp_path / "bad.html"
    bad.write_text("<p>This treatment is not allowed.</p>\n", encoding="utf-8")

    findings = copy_audit.scan_file(bad, brands=BANNED_BRANDS)

    assert findings
    assert findings[0].word == "treat"
    assert findings[0].line == 1
    assert "bad.html:1" in str(findings[0])


def test_the_exact_disclaimer_is_the_only_medical_exception():
    assert copy_audit.scan_text(copy.DISCLAIMER, file="x.html") == []
    findings = copy_audit.scan_text("This is a medical diagnosis.", file="x.html")
    assert [finding.word for finding in findings] == ["diagnos"]


def test_youcam_is_only_allowed_in_the_listed_contexts():
    assert copy_audit.scan_text("<p>YouCam</p>", file="x.html")
    assert copy_audit.scan_text("<p>Powered by YouCam API</p>", file="x.html") == []
    assert (
        copy_audit.scan_text("<p>YouCam</p>", file="consent.html", allow_youcam=True)
        == []
    )


def test_the_brand_list_is_configurable():
    findings = copy_audit.scan_text("Try Acme Skin.", file="x.html", brands=["acme skin"])

    assert [finding.word for finding in findings] == ["acme skin"]


def test_try_page_says_15_skin_aspects_plus_skin_type():
    text = (TEMPLATES / "try.html").read_text(encoding="utf-8")

    assert "16 skin aspects" not in text
    assert "15 skin aspects plus skin type" in text


def test_baseline_copy_says_counted_as_noise():
    assert "counted as noise" in copy.BASELINE_INTRO
    assert "treated as noise" not in copy.BASELINE_INTRO


# -- generated outputs -------------------------------------------------------


def test_routine_and_verdict_outputs_are_clean():
    scores = {aspect: 80.0 for aspect in NUMERIC_ASPECTS}
    scores.update(oiliness=20.0, redness=25.0, texture=30.0)
    bands = {
        aspect: {
            "band": 3.0,
            "floor_applied": True,
            "unstable": noise.is_unstable(3.0),
        }
        for aspect in NUMERIC_ASPECTS
    }
    plan = routine.build_routine(
        {
            "id": 1,
            "captured_at": "2026-10-24T15:00:00.000Z",
            "data_label": "SAMPLE",
            "scores": scores,
        },
        bands,
    )
    items = shopping.build_shopping_list([*plan.am, *plan.pm], [])
    routine_texts = (
        [item.display for item in (*plan.am, *plan.pm)]
        + [alt for item in (*plan.am, *plan.pm) for alt in item.alternatives]
        + [item.name for item in items]
        + plan.notes
        + plan.am_notes
        + plan.pm_notes
        + [copy.ROUTINE_FOOTER]
    )

    product = {
        "id": 1,
        "started_on": "2026-10-10",
        "target_aspects": ["moisture"],
        "data_label": "SAMPLE",
    }
    captures = [
        {
            "id": 1,
            "captured_on": "2026-10-08",
            "data_label": "SAMPLE",
            "source": "camera_kit",
            "status": "success",
            "scores": {aspect: 50.0 for aspect in NUMERIC_ASPECTS},
        },
        {
            "id": 2,
            "captured_on": "2026-10-09",
            "data_label": "SAMPLE",
            "source": "camera_kit",
            "status": "success",
            "scores": {aspect: 50.0 for aspect in NUMERIC_ASPECTS},
        },
        {
            "id": 3,
            "captured_on": "2026-10-24",
            "data_label": "SAMPLE",
            "source": "camera_kit",
            "status": "success",
            "scores": {**{aspect: 50.0 for aspect in NUMERIC_ASPECTS}, "moisture": 59.0},
        },
    ]
    computed = verdict.compute_verdict(
        product,
        captures,
        {"moisture": {"band": 4.0, "floor_applied": False, "unstable": False}},
        [],
        date(2026, 10, 30),
    )
    verdict_texts = (
        [computed.message, computed.label]
        + computed.warnings
        + [target.note for target in computed.targets]
        + [str(change["label"]) for change in computed.top_changes]
    )

    findings: list[copy_audit.Finding] = []
    for text in (*routine_texts, *verdict_texts):
        findings.extend(
            copy_audit.scan_text(text, file="<output>", brands=BANNED_BRANDS)
        )
    assert not findings, copy_audit.format_findings(findings)


def test_ui_score_is_absent_from_templates_js_and_series(env, web):
    for path in (*TEMPLATES.glob("*.html"), *STATIC.glob("*.js")):
        assert "ui_score" not in path.read_text(encoding="utf-8").lower(), path

    person_id, _ = seed_audit_data(env)
    login(web)

    response = web.get(f"/api/people/{person_id}/series")

    assert response.status_code == 200
    assert "ui_score" not in response.text


# -- rendered pages ----------------------------------------------------------


def test_rendered_pages_have_the_disclaimer_and_attestation(env, web):
    person_id, product_id = seed_audit_data(env)
    login(web)
    paths = [
        "/",
        "/try",
        "/people",
        f"/people/{person_id}/consent",
        f"/people/{person_id}/capture",
        f"/people/{person_id}/timeline",
        f"/products/{product_id}/verdict",
        f"/people/{person_id}/routine",
        f"/people/{person_id}/baseline",
        f"/people/{person_id}/products",
        "/privacy",
    ]

    for path in paths:
        response = web.get(path)
        assert response.status_code == 200, path
        assert copy.DISCLAIMER in response.text, path
        allow_youcam = path == "/privacy" or path.endswith("/consent")
        findings = copy_audit.scan_text(
            response.text,
            file=path,
            brands=BANNED_BRANDS,
            allow_youcam=allow_youcam,
        )
        assert not findings, f"{path}: {copy_audit.format_findings(findings)}"

    capture_page = web.get(f"/people/{person_id}/capture")
    assert copy.ATTESTATION in capture_page.text

    home = web.get("/")
    assert "Niacinamide serum (SAMPLE)" in home.text

    web.cookies.clear()
    anonymous_home = web.get("/")
    assert copy.DISCLAIMER in anonymous_home.text
    assert "Niacinamide serum (SAMPLE)" not in anonymous_home.text

    login(web)
    baseline = web.get(f"/people/{person_id}/baseline")
    assert baseline.status_code == 200
    assert "counted as noise" in baseline.text
    assert "treated as noise" not in baseline.text
