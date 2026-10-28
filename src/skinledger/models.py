"""Dataclasses for database rows and API results shared across modules."""

from dataclasses import dataclass


@dataclass(slots=True)
class Person:
    id: int
    display_name: str
    owner_token_hash: str
    is_demo_public: bool
    is_admin_owned: bool
    created_at: str


@dataclass(slots=True)
class Consent:
    id: int
    person_id: int
    consent_version: str
    adult_confirmed: bool
    accepted_at: str
    revoked_at: str | None


@dataclass(slots=True)
class Capture:
    id: int
    person_id: int
    owner_token_hash: str
    captured_at: str
    data_label: str
    source: str
    attested_at: str | None
    is_admin: bool
    width: int | None
    height: int | None
    file_id: str | None
    task_id: str | None
    status: str
    error_code: str | None
    error_message: str | None
    units_charged: int
    raw_result_json: str | None
    is_baseline_pair: bool
    created_at: str


@dataclass(slots=True)
class AspectScore:
    capture_id: int
    aspect: str
    raw_score: float | None
    value_text: str | None


@dataclass(slots=True)
class Mask:
    id: int
    capture_id: int
    aspect: str
    file_path: str


@dataclass(slots=True)
class NoiseBand:
    person_id: int
    aspect: str
    band: float
    a_capture_id: int
    b_capture_id: int
    floor_applied: bool
    computed_at: str


@dataclass(slots=True)
class Product:
    id: int
    person_id: int
    name: str
    category: str
    started_on: str
    ended_on: str | None
    target_aspects: str
    data_label: str


@dataclass(slots=True)
class Verdict:
    id: int
    product_id: int
    check_window: str
    outcome: str
    payload_json: str
    computed_at: str


@dataclass(slots=True)
class ApiUsage:
    id: int
    capture_id: int | None
    owner_token_hash: str
    day: str
    units: int
    mode: str
    is_admin: bool
    created_at: str
