"""Home page data: the browser's active products and their current verdict (P11)."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import Request

from skinledger import copy, guards, usage, verdict_store
from skinledger.db import connect, db_path

ACTIVE_PRODUCTS = (
    "SELECT pr.id, pr.name, pr.started_on, pr.data_label, "
    "p.id AS person_id, p.display_name "
    "FROM products pr JOIN persons p ON p.id = pr.person_id "
    "WHERE pr.ended_on IS NULL"
)
ORDER = " ORDER BY pr.started_on, pr.id"


def _next_checkin(started_on: str, today: date) -> tuple[str | None, str | None]:
    """The next scheduled check-in (GT date), or None once both windows passed."""
    started = date.fromisoformat(started_on)
    for days, label in ((14, copy.VERDICT_DAY_14), (28, copy.VERDICT_DAY_28)):
        when = started + timedelta(days=days)
        if today <= when:
            return label, when.isoformat()
    return None, None


def home_context(request: Request) -> dict[str, object]:
    """Owner-only cards; the public demo profile stays closed until P14."""
    admin = guards.is_admin_request(request)
    token = guards.owner_token_from_request(request)
    show = admin or token is not None
    cards: list[dict[str, object]] = []
    path = db_path()
    if show and path.is_file():
        conn = connect(path)
        try:
            if admin:
                rows = conn.execute(ACTIVE_PRODUCTS + ORDER).fetchall()
            else:
                rows = conn.execute(
                    ACTIVE_PRODUCTS + " AND p.owner_token_hash = ?" + ORDER,
                    (guards.owner_token_hash(token),),
                ).fetchall()
            today = usage.guatemala_day()
            for row in rows:
                computed = verdict_store.compute_for_product(
                    conn, int(row["id"]), today
                )
                if computed is None:
                    continue
                checkin_label, checkin_date = _next_checkin(row["started_on"], today)
                cards.append(
                    {
                        "product_id": int(row["id"]),
                        "name": row["name"],
                        "person_id": int(row["person_id"]),
                        "person_name": row["display_name"],
                        "outcome": computed.outcome,
                        "outcome_label": copy.verdict_outcome_label(computed.outcome),
                        "message": computed.message,
                        "label": computed.label,
                        "next_checkin_label": checkin_label,
                        "next_checkin_date": checkin_date,
                    }
                )
        finally:
            conn.close()
    return {"product_cards": cards, "show_home_products": show}
