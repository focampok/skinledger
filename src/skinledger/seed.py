"""SIMULATED demo data seeding; never generates photos or masks (P14).

--sample-person creates the public read-only sample profile (all SIMULATED).
--attach-to adds SIMULATED history to a real person without touching real rows.
--purge-simulated removes only seed rows (source='seed') and sample products.
"""

from __future__ import annotations

import argparse
import json
import random
import sqlite3
from datetime import UTC, date, datetime, timedelta

from skinledger import guards, logs, noise, usage, verdict_store
from skinledger.aspects import NUMERIC_ASPECTS
from skinledger.config import get_settings
from skinledger.db import connect, db_path, init_db

SAMPLE_PERSON = "Sample user (SIMULATED)"
NIACINAMIDE = "Niacinamide serum (SAMPLE)"
HYDRATING = "Hydrating cream (SAMPLE)"
SEED_RNG = 42
HISTORY_DAYS_AGO = 40
SECOND_PRODUCT_DELAY = 10
SEED_SOURCE = "seed"


def _require_admin() -> None:
    """Presence check only; the token value is never printed or logged."""
    token = get_settings().admin_token
    value = token.get_secret_value() if token is not None else ""
    if not value:
        raise SystemExit("ADMIN_TOKEN is required to run the seed; refusing to continue.")


def _at(day: date, hour: int = 15, minute: int = 0) -> str:
    return f"{day.isoformat()}T{hour:02d}:{minute:02d}:00.000Z"


def _guatemala_date(value: object) -> date:
    text = str(value or "")
    try:
        moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return date.fromisoformat(text[:10])
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return usage.guatemala_day(moment)


def _noisy(
    baseline: dict[str, float],
    rng: random.Random,
    overrides: dict[str, float] | None = None,
) -> dict[str, float]:
    scores = {
        aspect: round(float(baseline.get(aspect, 50.0)) + rng.gauss(0, 1.5), 1)
        for aspect in NUMERIC_ASPECTS
    }
    for aspect, value in (overrides or {}).items():
        scores[aspect] = round(float(value), 1)
    return scores


def _mean_scores(scores_list: list[dict[str, float]]) -> dict[str, float]:
    return {
        aspect: round(
            sum(scores.get(aspect, 50.0) for scores in scores_list)
            / len(scores_list),
            1,
        )
        for aspect in NUMERIC_ASPECTS
    }


def _insert_capture(
    conn: sqlite3.Connection,
    person_id: int,
    person_hash: str,
    when: str,
    scores: dict[str, float],
    *,
    baseline_pair: bool = False,
) -> int:
    capture_id = int(
        conn.execute(
            "INSERT INTO captures (person_id, owner_token_hash, captured_at, data_label, "
            "source, status, is_baseline_pair) "
            "VALUES (?, ?, ?, 'SIMULATED', 'seed', 'success', ?)",
            (person_id, person_hash, when, int(baseline_pair)),
        ).lastrowid
    )
    for aspect, value in scores.items():
        conn.execute(
            "INSERT INTO aspect_scores (capture_id, aspect, raw_score) VALUES (?, ?, ?)",
            (capture_id, aspect, value),
        )
    return capture_id


def _insert_bands(
    conn: sqlite3.Connection,
    person_id: int,
    a_capture_id: int,
    b_capture_id: int,
    bands: dict[str, float],
) -> None:
    now = usage.utc_now_iso()
    for aspect in NUMERIC_ASPECTS:
        conn.execute(
            "INSERT INTO noise_bands (person_id, aspect, band, a_capture_id, "
            "b_capture_id, floor_applied, computed_at) VALUES (?, ?, ?, ?, ?, 0, ?)",
            (
                person_id,
                aspect,
                bands[aspect],
                a_capture_id,
                b_capture_id,
                now,
            ),
        )


def _insert_product(
    conn: sqlite3.Connection,
    person_id: int,
    name: str,
    category: str,
    started_on: date,
    targets: list[str],
) -> int:
    return int(
        conn.execute(
            "INSERT INTO products (person_id, name, category, started_on, "
            "target_aspects, data_label) VALUES (?, ?, ?, ?, ?, 'SAMPLE')",
            (person_id, name, category, started_on.isoformat(), json.dumps(targets)),
        ).lastrowid
    )


def _band_value(bands: dict[str, dict[str, object]], aspect: str) -> float:
    entry = bands.get(aspect)
    if entry is None or entry.get("band") is None:
        return 3.0
    return float(entry["band"])


def _warn_unstable(bands: dict[str, dict[str, object]], targets: list[str]) -> None:
    for aspect in targets:
        entry = bands.get(aspect)
        if entry is None:
            print(
                f"warning: {aspect} has no baseline band; it will not count in the verdict."
            )
        elif entry.get("unstable"):
            print(
                f"warning: {aspect} is unstable for this person; it will not count in the verdict."
            )


def _print_verdicts(
    conn: sqlite3.Connection, product_ids: list[int], today: date
) -> None:
    for product_id in product_ids:
        row = conn.execute(
            "SELECT name FROM products WHERE id = ?", (product_id,)
        ).fetchone()
        if row is None:
            continue
        computed = verdict_store.compute_for_product(conn, product_id, today)
        if computed is None:
            continue
        print(f"{row['name']}: {computed.outcome} — {computed.message}")
        for warning in computed.warnings:
            print(f"warning: {row['name']}: {warning}")


def _purge_demo_persons(conn: sqlite3.Connection) -> int:
    count = int(conn.execute("DELETE FROM persons WHERE is_demo_public = 1").rowcount)
    conn.commit()
    return count


def _purge_person_seed_rows(conn: sqlite3.Connection, person_id: int) -> tuple[int, int]:
    captures = int(
        conn.execute(
            "DELETE FROM captures WHERE person_id = ? AND source = 'seed'",
            (person_id,),
        ).rowcount
    )
    products = int(
        conn.execute(
            "DELETE FROM products WHERE person_id = ? "
            "AND data_label IN ('SIMULATED', 'SAMPLE')",
            (person_id,),
        ).rowcount
    )
    conn.commit()
    return captures, products


def create_sample_person(
    conn: sqlite3.Connection, today: date, rng: random.Random
) -> tuple[int, list[int]]:
    """The public sample profile: SIMULATED bands 3–6 and two clean verdicts."""
    _purge_demo_persons(conn)
    start = today - timedelta(days=HISTORY_DAYS_AGO)
    person_hash = guards.admin_owner_hash()
    person_id = int(
        conn.execute(
            "INSERT INTO persons (display_name, owner_token_hash, is_demo_public, "
            "is_admin_owned) VALUES (?, ?, 1, 1)",
            (SAMPLE_PERSON, person_hash),
        ).lastrowid
    )
    baseline = {aspect: round(rng.uniform(45, 75), 1) for aspect in NUMERIC_ASPECTS}
    bands = {aspect: round(rng.uniform(3.0, 6.0), 1) for aspect in NUMERIC_ASPECTS}

    scores_a = _noisy(baseline, rng)
    scores_b = _noisy(baseline, rng)
    first = _insert_capture(
        conn, person_id, person_hash, _at(start, 15, 0), scores_a, baseline_pair=True
    )
    second = _insert_capture(
        conn, person_id, person_hash, _at(start, 15, 3), scores_b, baseline_pair=True
    )
    _insert_bands(conn, person_id, first, second, bands)
    pair_mean = _mean_scores([scores_a, scores_b])

    second_start = start + timedelta(days=SECOND_PRODUCT_DELAY)
    second_baseline = _noisy(baseline, rng)
    _insert_capture(
        conn,
        person_id,
        person_hash,
        _at(second_start - timedelta(days=2)),
        second_baseline,
    )

    niacinamide_14 = _noisy(
        pair_mean,
        rng,
        {
            "oiliness": pair_mean["oiliness"] + 1.5 * bands["oiliness"],
            "pore": pair_mean["pore"] + 0.5 * bands["pore"],
        },
    )
    niacinamide_28 = _noisy(
        pair_mean,
        rng,
        {
            "oiliness": pair_mean["oiliness"] + 2.0 * bands["oiliness"],
            "pore": pair_mean["pore"] + 0.5 * bands["pore"],
        },
    )
    _insert_capture(
        conn, person_id, person_hash, _at(start + timedelta(days=14)), niacinamide_14
    )
    _insert_capture(
        conn, person_id, person_hash, _at(start + timedelta(days=28)), niacinamide_28
    )

    hydrating_14 = _noisy(
        second_baseline,
        rng,
        {
            "moisture": second_baseline["moisture"] + 0.5 * bands["moisture"],
            "texture": second_baseline["texture"] - 0.5 * bands["texture"],
        },
    )
    hydrating_28 = _noisy(
        second_baseline,
        rng,
        {
            "moisture": second_baseline["moisture"] + 0.5 * bands["moisture"],
            "texture": second_baseline["texture"] - 0.5 * bands["texture"],
        },
    )
    _insert_capture(
        conn,
        person_id,
        person_hash,
        _at(second_start + timedelta(days=14)),
        hydrating_14,
    )
    _insert_capture(
        conn,
        person_id,
        person_hash,
        _at(second_start + timedelta(days=28)),
        hydrating_28,
    )

    products = [
        _insert_product(
            conn, person_id, NIACINAMIDE, "serum", start, ["oiliness", "pore"]
        ),
        _insert_product(
            conn,
            person_id,
            HYDRATING,
            "moisturizer",
            second_start,
            ["moisture", "texture"],
        ),
    ]
    conn.commit()
    logs.log_event(
        "seed.created",
        persons=1,
        captures=7,
        products=2,
        bands=len(bands),
    )
    return person_id, products


def ensure_sample_person(
    conn: sqlite3.Connection, today: date, rng: random.Random | None = None
) -> int:
    """Startup helper: create the public sample only when it is missing."""
    row = conn.execute(
        "SELECT id FROM persons WHERE is_demo_public = 1 ORDER BY id LIMIT 1"
    ).fetchone()
    if row is not None:
        return int(row["id"])
    person_id, _ = create_sample_person(conn, today, rng or random.Random(SEED_RNG))
    return person_id


def _scores_for(conn: sqlite3.Connection, capture_id: int) -> dict[str, float]:
    rows = conn.execute(
        "SELECT aspect, raw_score FROM aspect_scores "
        "WHERE capture_id = ? AND raw_score IS NOT NULL",
        (capture_id,),
    ).fetchall()
    return {row["aspect"]: float(row["raw_score"]) for row in rows}


def attach_history(
    conn: sqlite3.Connection, person_id: int, today: date, rng: random.Random
) -> list[int]:
    """Add SIMULATED history to a real person, using only noise.get_bands bands."""
    person = conn.execute(
        "SELECT * FROM persons WHERE id = ?", (person_id,)
    ).fetchone()
    if person is None:
        raise SystemExit("Person not found.")
    if person["is_demo_public"]:
        raise SystemExit("--attach-to needs a real person, not the public sample.")
    bands = noise.get_bands(person_id, conn=conn)
    if not bands:
        raise SystemExit("Take 2 baseline captures first.")

    pair = conn.execute(
        "SELECT * FROM captures WHERE person_id = ? AND status = 'success' "
        "AND is_baseline_pair = 1 ORDER BY captured_at, id",
        (person_id,),
    ).fetchall()
    if len(pair) < 2:
        raise SystemExit("Take 2 baseline captures first.")
    pair = pair[-2:]
    start = _guatemala_date(pair[0]["captured_at"])
    baseline = _mean_scores(
        [_scores_for(conn, int(pair[0]["id"])), _scores_for(conn, int(pair[1]["id"]))]
    )
    targets = ["oiliness", "pore", "moisture", "texture"]
    _warn_unstable(bands, targets)

    purged_captures, purged_products = _purge_person_seed_rows(conn, person_id)
    if purged_captures or purged_products:
        logs.log_event(
            "seed.purged",
            captures=purged_captures,
            products=purged_products,
        )

    person_hash = str(person["owner_token_hash"])
    second_start = start + timedelta(days=SECOND_PRODUCT_DELAY)
    second_baseline = _noisy(baseline, rng)
    _insert_capture(
        conn,
        person_id,
        person_hash,
        _at(second_start - timedelta(days=2)),
        second_baseline,
    )

    oil_band = _band_value(bands, "oiliness")
    pore_band = _band_value(bands, "pore")
    moisture_band = _band_value(bands, "moisture")
    texture_band = _band_value(bands, "texture")

    niacinamide_14 = _noisy(
        baseline,
        rng,
        {
            "oiliness": baseline["oiliness"] + 1.5 * oil_band,
            "pore": baseline["pore"] + 0.5 * pore_band,
        },
    )
    niacinamide_28 = _noisy(
        baseline,
        rng,
        {
            "oiliness": baseline["oiliness"] + 2.0 * oil_band,
            "pore": baseline["pore"] + 0.5 * pore_band,
        },
    )
    _insert_capture(
        conn, person_id, person_hash, _at(start + timedelta(days=14)), niacinamide_14
    )
    _insert_capture(
        conn, person_id, person_hash, _at(start + timedelta(days=28)), niacinamide_28
    )

    hydrating_14 = _noisy(
        second_baseline,
        rng,
        {
            "moisture": second_baseline["moisture"] + 0.5 * moisture_band,
            "texture": second_baseline["texture"] - 0.5 * texture_band,
        },
    )
    hydrating_28 = _noisy(
        second_baseline,
        rng,
        {
            "moisture": second_baseline["moisture"] + 0.5 * moisture_band,
            "texture": second_baseline["texture"] - 0.5 * texture_band,
        },
    )
    _insert_capture(
        conn,
        person_id,
        person_hash,
        _at(second_start + timedelta(days=14)),
        hydrating_14,
    )
    _insert_capture(
        conn,
        person_id,
        person_hash,
        _at(second_start + timedelta(days=28)),
        hydrating_28,
    )

    products = [
        _insert_product(
            conn, person_id, NIACINAMIDE, "serum", start, ["oiliness", "pore"]
        ),
        _insert_product(
            conn,
            person_id,
            HYDRATING,
            "moisturizer",
            second_start,
            ["moisture", "texture"],
        ),
    ]
    conn.commit()
    logs.log_event("seed.created", captures=5, products=2)
    return products


def purge_simulated(conn: sqlite3.Connection) -> tuple[int, int, int]:
    """Delete only the public sample person, seed captures and sample products."""
    persons = int(conn.execute("DELETE FROM persons WHERE is_demo_public = 1").rowcount)
    captures = int(
        conn.execute("DELETE FROM captures WHERE source = 'seed'").rowcount
    )
    products = int(
        conn.execute(
            "DELETE FROM products WHERE data_label IN ('SIMULATED', 'SAMPLE')"
        ).rowcount
    )
    conn.commit()
    logs.log_event(
        "seed.purged", persons=persons, captures=captures, products=products
    )
    return persons, captures, products


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Create or purge SIMULATED SkinLedger demo data."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--sample-person",
        action="store_true",
        help="create the public read-only sample profile",
    )
    group.add_argument(
        "--attach-to",
        type=int,
        metavar="PERSON_ID",
        help="add SIMULATED history to a real person",
    )
    group.add_argument(
        "--purge-simulated",
        action="store_true",
        help="delete only seed rows and sample products",
    )
    args = parser.parse_args(argv)

    _require_admin()
    init_db()
    conn = connect(db_path())
    try:
        today = usage.guatemala_day()
        rng = random.Random(SEED_RNG)
        if args.sample_person:
            person_id, products = create_sample_person(conn, today, rng)
            print(f"Sample person id: {person_id}")
            _print_verdicts(conn, products, today)
        elif args.attach_to is not None:
            products = attach_history(conn, args.attach_to, today, rng)
            _print_verdicts(conn, products, today)
        else:
            persons, captures, products = purge_simulated(conn)
            print(
                f"Purged {persons} sample person(s), {captures} seed capture(s), "
                f"{products} sample product(s)."
            )
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
