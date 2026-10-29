"""P14 acceptance tests: SIMULATED seed, public read-only demo and banners."""

from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from skinledger import config, copy, copy_audit, guards, noise, seed, usage
from skinledger.aspects import NUMERIC_ASPECTS
from skinledger.db import connect, db_path, init_db
from skinledger.web.app import app

OWNER_TOKEN = "owner-token"


@pytest.fixture
def env(tmp_path, monkeypatch):
    settings = config.settings
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    monkeypatch.setattr(settings, "youcam_mock", True)
    monkeypatch.setattr(settings, "invite_code", SecretStr("invite-ok"))
    monkeypatch.setattr(settings, "admin_token", SecretStr("test-admin-token"))
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
    when: str,
    scores: dict[str, float],
    *,
    data_label: str = "REAL",
    source: str = "camera_kit",
    baseline_pair: bool = False,
) -> int:
    capture_id = int(
        conn.execute(
            "INSERT INTO captures (person_id, owner_token_hash, captured_at, data_label, "
            "source, status, is_baseline_pair) "
            "VALUES (?, ?, ?, ?, ?, 'success', ?)",
            (
                person_id,
                guards.owner_token_hash(OWNER_TOKEN),
                when,
                data_label,
                source,
                int(baseline_pair),
            ),
        ).lastrowid
    )
    for aspect, value in scores.items():
        conn.execute(
            "INSERT INTO aspect_scores (capture_id, aspect, raw_score) VALUES (?, ?, ?)",
            (capture_id, aspect, value),
        )
    return capture_id


def seed_real_person(
    env, *, unstable_pore: bool = True, with_product: bool = True
) -> tuple[int, int | None]:
    start = usage.guatemala_day() - timedelta(days=40)
    conn = connect(db_path())
    try:
        person_id = int(
            conn.execute(
                "INSERT INTO persons (display_name, owner_token_hash) VALUES (?, ?)",
                ("Real user", guards.owner_token_hash(OWNER_TOKEN)),
            ).lastrowid
        )
        first = {aspect: 50.0 for aspect in NUMERIC_ASPECTS}
        second = dict(first)
        if unstable_pore:
            second["pore"] = 63.0
        _insert_capture(
            conn,
            person_id,
            f"{start.isoformat()}T15:00:00.000Z",
            first,
            baseline_pair=True,
        )
        _insert_capture(
            conn,
            person_id,
            f"{start.isoformat()}T15:03:00.000Z",
            second,
            baseline_pair=True,
        )
        product_id = None
        if with_product:
            product_id = int(
                conn.execute(
                    "INSERT INTO products (person_id, name, category, started_on, "
                    "target_aspects, data_label) VALUES (?, 'Real serum', 'serum', ?, "
                    "'[\"moisture\"]', 'REAL')",
                    (person_id, start.isoformat()),
                ).lastrowid
            )
        conn.commit()
        noise.compute_band(person_id, conn=conn)
    finally:
        conn.close()
    return person_id, product_id


def _demo_state(conn) -> tuple[int, list[int], int]:
    person = conn.execute(
        "SELECT id FROM persons WHERE is_demo_public = 1"
    ).fetchone()
    products = [
        int(row["id"])
        for row in conn.execute(
            "SELECT id FROM products WHERE person_id = ? ORDER BY id",
            (person["id"],),
        )
    ]
    capture = conn.execute(
        "SELECT id FROM captures WHERE person_id = ? ORDER BY id LIMIT 1",
        (person["id"],),
    ).fetchone()
    return int(person["id"]), products, int(capture["id"])


def _counts() -> dict[str, int]:
    conn = connect(db_path())
    try:
        return {
            table: int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in (
                "persons",
                "captures",
                "products",
                "noise_bands",
                "masks",
                "api_usage",
                "verdicts",
            )
        }
    finally:
        conn.close()


# -- seed --------------------------------------------------------------------


def test_the_seed_refuses_without_admin_token(env, monkeypatch):
    monkeypatch.setattr(config.settings, "admin_token", SecretStr(""))

    with pytest.raises(SystemExit) as excinfo:
        seed.main(["--sample-person"])

    assert "ADMIN_TOKEN" in str(excinfo.value)
    assert _counts()["persons"] == 0


def test_sample_person_creates_the_public_demo(env, capsys):
    assert seed.main(["--sample-person"]) == 0
    out = capsys.readouterr().out
    assert "Niacinamide serum (SAMPLE): keep" in out
    assert "Hydrating cream (SAMPLE): no_change" in out

    conn = connect(db_path())
    try:
        person = conn.execute(
            "SELECT * FROM persons WHERE is_demo_public = 1"
        ).fetchone()
        assert person["display_name"] == seed.SAMPLE_PERSON
        bands = conn.execute(
            "SELECT * FROM noise_bands WHERE person_id = ?", (person["id"],)
        ).fetchall()
        assert len(bands) == 15
        assert all(3.0 <= row["band"] <= 6.0 for row in bands)
        assert all(not noise.is_unstable(row["band"]) for row in bands)

        captures = conn.execute(
            "SELECT * FROM captures WHERE person_id = ?", (person["id"],)
        ).fetchall()
        assert len(captures) == 7
        assert all(
            row["data_label"] == "SIMULATED" and row["source"] == "seed"
            for row in captures
        )
        assert conn.execute("SELECT COUNT(*) FROM masks").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM api_usage").fetchone()[0] == 0

        products = conn.execute(
            "SELECT * FROM products WHERE person_id = ? ORDER BY id", (person["id"],)
        ).fetchall()
        assert len(products) == 2
        assert all(row["name"].endswith("(SAMPLE)") for row in products)
        assert all(row["data_label"] == "SAMPLE" for row in products)
        for row in products:
            assert copy_audit.scan_text(row["name"], file="seed") == []
        outcomes = {
            row["outcome"]
            for row in conn.execute("SELECT outcome FROM verdicts").fetchall()
        }
        assert outcomes == {"keep", "no_change"}
    finally:
        conn.close()

    assert not (env.data_dir / "masks").exists()
    assert not list(env.data_dir.glob("**/*.png"))


def test_sample_person_is_idempotent(env):
    seed.main(["--sample-person"])
    first = _counts()
    seed.main(["--sample-person"])
    second = _counts()

    assert first["persons"] == second["persons"] == 1
    assert first["captures"] == second["captures"] == 7
    assert first["products"] == second["products"] == 2
    assert first["noise_bands"] == second["noise_bands"] == 15


def test_attach_keeps_keep_even_with_an_unstable_pore(env, capsys):
    person_id, _ = seed_real_person(
        env, unstable_pore=True, with_product=False
    )

    assert seed.main(["--attach-to", str(person_id)]) == 0
    out = capsys.readouterr().out
    assert "pore is unstable" in out
    assert "Niacinamide serum (SAMPLE): keep" in out
    assert "Hydrating cream (SAMPLE): no_change" in out

    conn = connect(db_path())
    try:
        real = conn.execute(
            "SELECT COUNT(*) FROM captures WHERE person_id = ? AND source = 'camera_kit'",
            (person_id,),
        ).fetchone()[0]
        simulated = conn.execute(
            "SELECT COUNT(*) FROM captures WHERE person_id = ? AND source = 'seed'",
            (person_id,),
        ).fetchone()[0]
        products = conn.execute(
            "SELECT COUNT(*) FROM products WHERE person_id = ?", (person_id,)
        ).fetchone()[0]
    finally:
        conn.close()
    assert real == 2
    assert simulated == 5
    assert products == 2

    seed.main(["--attach-to", str(person_id)])
    conn = connect(db_path())
    try:
        again = conn.execute(
            "SELECT COUNT(*) FROM captures WHERE person_id = ? AND source = 'seed'",
            (person_id,),
        ).fetchone()[0]
        again_products = conn.execute(
            "SELECT COUNT(*) FROM products WHERE person_id = ?", (person_id,)
        ).fetchone()[0]
    finally:
        conn.close()
    assert again == 5
    assert again_products == 2


def test_purge_removes_only_seed_rows(env):
    real_person, real_product = seed_real_person(env)
    seed.main(["--sample-person"])
    seed.main(["--attach-to", str(real_person)])

    seed.main(["--purge-simulated"])

    conn = connect(db_path())
    try:
        assert (
            conn.execute("SELECT COUNT(*) FROM persons WHERE is_demo_public = 1").fetchone()[0]
            == 0
        )
        assert (
            conn.execute("SELECT COUNT(*) FROM captures WHERE source = 'seed'").fetchone()[0]
            == 0
        )
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM products WHERE data_label IN ('SIMULATED', 'SAMPLE')"
            ).fetchone()[0]
            == 0
        )
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM captures WHERE person_id = ? AND source = 'camera_kit'",
                (real_person,),
            ).fetchone()[0]
            == 2
        )
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM persons WHERE id = ?", (real_person,)
            ).fetchone()[0]
            == 1
        )
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM products WHERE id = ?", (real_product,)
            ).fetchone()[0]
            == 1
        )
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM noise_bands WHERE person_id = ?", (real_person,)
            ).fetchone()[0]
            == 15
        )
    finally:
        conn.close()

    seed.main(["--purge-simulated"])
    assert _counts()["persons"] == 1  # the real person only


# -- public read-only demo ---------------------------------------------------


def test_public_demo_pages_are_viewable_and_read_only(env, web):
    seed.main(["--sample-person"])
    conn = connect(db_path())
    try:
        demo_id, product_ids, capture_id = _demo_state(conn)
    finally:
        conn.close()
    web.cookies.clear()

    read_paths = [
        f"/people/{demo_id}/timeline",
        f"/api/people/{demo_id}/series",
        f"/people/{demo_id}/baseline",
        f"/people/{demo_id}/products",
        f"/people/{demo_id}/routine",
        *[f"/products/{product_id}/verdict" for product_id in product_ids],
    ]
    for path in read_paths:
        response = web.get(path)
        assert response.status_code == 200, path

    for path in (
        f"/people/{demo_id}/timeline",
        f"/people/{demo_id}/baseline",
        f"/people/{demo_id}/products",
        f"/people/{demo_id}/routine",
    ):
        assert copy.SAMPLE_PROFILE_BANNER in web.get(path).text, path
    verdict = web.get(f"/products/{product_ids[0]}/verdict")
    assert copy.SAMPLE_PROFILE_BANNER in verdict.text
    assert copy.VERDICT_TAKE_CHECKIN not in verdict.text

    products_page = web.get(f"/people/{demo_id}/products")
    assert copy.DEMO_READ_ONLY in products_page.text
    assert 'id="product-name"' not in products_page.text
    assert f"/people/{demo_id}/capture" not in products_page.text
    assert (
        f'hx-post="/people/{demo_id}/products/{product_ids[0]}/end"'
        not in products_page.text
    )
    for path in (f"/people/{demo_id}/timeline", f"/people/{demo_id}/routine"):
        assert f"/people/{demo_id}/capture" not in web.get(path).text

    people = web.get("/people")
    assert seed.SAMPLE_PERSON in people.text
    try_page = web.get("/try")
    assert f"/people/{demo_id}/timeline" in try_page.text

    relative = f"masks/{demo_id}/{capture_id}/moisture_0.png"
    path = env.data_dir / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"PNG")
    conn = connect(db_path())
    try:
        conn.execute(
            "INSERT INTO masks (capture_id, aspect, file_path) VALUES (?, 'moisture', ?)",
            (capture_id, relative),
        )
        conn.commit()
    finally:
        conn.close()
    media = web.get(f"/media/{capture_id}/moisture_0.png")
    assert media.status_code == 200
    assert media.headers["cache-control"] == "no-store"

    assert (
        web.post(
            f"/api/captures?person_id={demo_id}&source=upload&attested=1",
            content=b"",
        ).status_code
        == 403
    )
    assert (
        web.post(
            f"/people/{demo_id}/products",
            data={
                "name": "Nope",
                "category": "serum",
                "started_on": usage.guatemala_today(),
                "target_aspects": "acne",
            },
        ).status_code
        == 403
    )
    assert (
        web.post(
            f"/people/{demo_id}/products/{product_ids[0]}/end"
        ).status_code
        == 403
    )
    assert (
        web.post(
            f"/people/{demo_id}/delete", data={"confirm_name": seed.SAMPLE_PERSON}
        ).status_code
        == 403
    )
    assert (
        web.post(
            f"/people/{demo_id}/consent",
            data={"adult_confirmed": "1", "agree": "1"},
        ).status_code
        == 403
    )

    real_id, real_product = seed_real_person(env, with_product=True)
    for path in (
        f"/people/{real_id}/timeline",
        f"/api/people/{real_id}/series",
        f"/people/{real_id}/baseline",
        f"/people/{real_id}/products",
        f"/people/{real_id}/routine",
        f"/products/{real_product}/verdict",
    ):
        assert web.get(path).status_code == 404, path


def test_attached_history_pages_show_the_demo_banner(env, web):
    person_id, _ = seed_real_person(env, unstable_pore=True)
    seed.main(["--attach-to", str(person_id)])
    login(web)

    for path in (
        f"/people/{person_id}/timeline",
        f"/people/{person_id}/baseline",
        f"/people/{person_id}/products",
        f"/people/{person_id}/routine",
    ):
        response = web.get(path)
        assert response.status_code == 200, path
        assert copy.VERDICT_SIMULATED_BANNER in response.text, path
        assert copy.SAMPLE_PROFILE_BANNER not in response.text

    conn = connect(db_path())
    try:
        product_id = conn.execute(
            "SELECT id FROM products WHERE person_id = ? AND name = ?",
            (person_id, seed.NIACINAMIDE),
        ).fetchone()["id"]
    finally:
        conn.close()
    verdict = web.get(f"/products/{product_id}/verdict")
    assert verdict.status_code == 200
    assert copy.VERDICT_SIMULATED_BANNER in verdict.text
    assert copy.VERDICT_TAKE_CHECKIN in verdict.text
