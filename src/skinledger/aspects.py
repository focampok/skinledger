"""The 16 SD aspects, their English UI labels and the numeric subset."""

SD_ACTIONS: tuple[str, ...] = (
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
)

ASPECT_LABELS: dict[str, str] = {
    "wrinkle": "Wrinkles",
    "droopy_upper_eyelid": "Upper eyelid droop",
    "droopy_lower_eyelid": "Lower eyelid droop",
    "firmness": "Firmness",
    "acne": "Acne",
    "moisture": "Moisture",
    "eye_bag": "Eye bags",
    "dark_circle_v2": "Dark circles",
    "age_spot": "Age spots",
    "radiance": "Radiance",
    "redness": "Redness",
    "oiliness": "Oiliness",
    "pore": "Pores",
    "texture": "Texture",
    "tear_trough": "Tear troughs",
    "skin_type": "Skin type",
}

NUMERIC_ASPECTS: tuple[str, ...] = tuple(
    aspect for aspect in SD_ACTIONS if aspect != "skin_type"
)
