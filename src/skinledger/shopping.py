"""Generic shopping list derived from the routine rules (P12).

No brands, no doses, no medicine amounts: only ingredient categories already
defined by plan §13. Items whose product category is covered by an active
product are removed.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from skinledger.routine import RoutineItem


@dataclass(slots=True)
class ShoppingItem:
    name: str
    category: str


def build_shopping_list(
    items: Iterable[RoutineItem], active_categories: Iterable[str]
) -> list[ShoppingItem]:
    """Deduplicated categories, minus what the person's active products cover."""
    active = {str(category) for category in active_categories}
    seen: set[str] = set()
    result: list[ShoppingItem] = []
    for item in items:
        if not item.category or item.category in active:
            continue
        if item.name in seen:
            continue
        seen.add(item.name)
        result.append(ShoppingItem(name=item.name, category=item.category))
    return result
