"""Generic shopping list derived from the routine rules (P12).

No brands, no doses, no medicine amounts: only ingredient categories already
defined by plan §13. Items whose product category is covered by an active
product are removed.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from skinledger.routine import RoutineItem

CATEGORY_ORDER = (
    "cleanser",
    "serum",
    "retinoid",
    "exfoliant",
    "eye cream",
    "moisturizer",
    "sunscreen",
)


@dataclass(slots=True)
class ShoppingItem:
    name: str
    category: str


def build_shopping_list(
    items: Iterable[RoutineItem], active_categories: Iterable[str]
) -> list[ShoppingItem]:
    """One line per product category, minus what active products already cover."""
    active = {str(category) for category in active_categories}
    by_category: dict[str, list[str]] = {}
    for item in items:
        if not item.category or item.category in active:
            continue
        names = by_category.setdefault(item.category, [])
        for name in (item.name, *item.alternatives):
            if name not in names:
                names.append(name)

    order = {category: index for index, category in enumerate(CATEGORY_ORDER)}
    return [
        ShoppingItem(name=" or ".join(names), category=category)
        for category, names in sorted(
            by_category.items(), key=lambda pair: order.get(pair[0], len(order))
        )
    ]
