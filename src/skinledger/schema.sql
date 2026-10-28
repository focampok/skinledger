-- SkinLedger SQLite schema.
-- Privacy: the original photo is never stored, so no table has a photo or image path column.
-- Raw scores only: aspect_scores has no ui_score column (it is discarded at parse time).
-- Foreign keys are enabled per connection in db.connect().

CREATE TABLE IF NOT EXISTS persons (
    id               INTEGER PRIMARY KEY,
    display_name     TEXT NOT NULL,
    owner_token_hash TEXT NOT NULL,
    is_demo_public   INTEGER NOT NULL DEFAULT 0 CHECK (is_demo_public IN (0, 1)),
    is_admin_owned   INTEGER NOT NULL DEFAULT 0 CHECK (is_admin_owned IN (0, 1)),
    created_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS consents (
    id              INTEGER PRIMARY KEY,
    person_id       INTEGER NOT NULL REFERENCES persons (id) ON DELETE CASCADE,
    consent_version TEXT NOT NULL,
    adult_confirmed INTEGER NOT NULL CHECK (adult_confirmed IN (0, 1)),
    accepted_at     TEXT NOT NULL,
    revoked_at      TEXT
);

CREATE TABLE IF NOT EXISTS captures (
    id               INTEGER PRIMARY KEY,
    person_id        INTEGER NOT NULL REFERENCES persons (id) ON DELETE CASCADE,
    owner_token_hash TEXT NOT NULL,
    captured_at      TEXT NOT NULL,
    data_label       TEXT NOT NULL CHECK (data_label IN ('REAL', 'SIMULATED', 'SAMPLE')),
    source           TEXT NOT NULL CHECK (source IN ('camera_kit', 'upload', 'seed', 'mock')),
    attested_at      TEXT,
    is_admin         INTEGER NOT NULL DEFAULT 0 CHECK (is_admin IN (0, 1)),
    width            INTEGER,
    height           INTEGER,
    file_id          TEXT,
    task_id          TEXT,
    status           TEXT NOT NULL CHECK (
        status IN ('queued', 'uploading', 'running', 'success', 'error', 'timeout')
    ),
    error_code       TEXT,
    error_message    TEXT,
    units_charged    INTEGER NOT NULL DEFAULT 0,
    raw_result_json  TEXT,
    is_baseline_pair INTEGER NOT NULL DEFAULT 0 CHECK (is_baseline_pair IN (0, 1)),
    created_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS aspect_scores (
    capture_id INTEGER NOT NULL REFERENCES captures (id) ON DELETE CASCADE,
    aspect     TEXT NOT NULL,
    raw_score  REAL,
    value_text TEXT,
    PRIMARY KEY (capture_id, aspect)
);

CREATE TABLE IF NOT EXISTS masks (
    id         INTEGER PRIMARY KEY,
    capture_id INTEGER NOT NULL REFERENCES captures (id) ON DELETE CASCADE,
    aspect     TEXT NOT NULL,
    file_path  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS noise_bands (
    person_id     INTEGER NOT NULL REFERENCES persons (id) ON DELETE CASCADE,
    aspect        TEXT NOT NULL,
    band          REAL NOT NULL,
    a_capture_id  INTEGER NOT NULL REFERENCES captures (id) ON DELETE CASCADE,
    b_capture_id  INTEGER NOT NULL REFERENCES captures (id) ON DELETE CASCADE,
    floor_applied INTEGER NOT NULL DEFAULT 0 CHECK (floor_applied IN (0, 1)),
    computed_at   TEXT NOT NULL,
    PRIMARY KEY (person_id, aspect)
);

CREATE TABLE IF NOT EXISTS products (
    id             INTEGER PRIMARY KEY,
    person_id      INTEGER NOT NULL REFERENCES persons (id) ON DELETE CASCADE,
    name           TEXT NOT NULL,
    category       TEXT NOT NULL,
    started_on     DATE NOT NULL,
    ended_on       DATE,
    target_aspects TEXT NOT NULL DEFAULT '[]',
    data_label     TEXT NOT NULL CHECK (data_label IN ('REAL', 'SIMULATED', 'SAMPLE'))
);

CREATE TABLE IF NOT EXISTS verdicts (
    id           INTEGER PRIMARY KEY,
    product_id   INTEGER NOT NULL REFERENCES products (id) ON DELETE CASCADE,
    check_window TEXT NOT NULL CHECK (check_window IN ('d14', 'd28')),
    outcome      TEXT NOT NULL CHECK (
        outcome IN ('keep', 'no_change', 'worse', 'too_early', 'no_band')
    ),
    payload_json TEXT NOT NULL,
    computed_at  TEXT NOT NULL
);

-- Usage rows survive profile deletion: capture_id becomes NULL so unit caps cannot be reset.
CREATE TABLE IF NOT EXISTS api_usage (
    id               INTEGER PRIMARY KEY,
    capture_id       INTEGER REFERENCES captures (id) ON DELETE SET NULL,
    owner_token_hash TEXT NOT NULL,
    day              DATE NOT NULL,
    units            INTEGER NOT NULL,
    mode             TEXT NOT NULL CHECK (mode IN ('real', 'mock')),
    is_admin         INTEGER NOT NULL DEFAULT 0 CHECK (is_admin IN (0, 1)),
    created_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_captures_person_time ON captures (person_id, captured_at);
CREATE INDEX IF NOT EXISTS idx_consents_person ON consents (person_id);
CREATE INDEX IF NOT EXISTS idx_masks_capture ON masks (capture_id);
CREATE INDEX IF NOT EXISTS idx_products_person ON products (person_id);
CREATE INDEX IF NOT EXISTS idx_verdicts_product ON verdicts (product_id);
CREATE INDEX IF NOT EXISTS idx_api_usage_day ON api_usage (day);
CREATE INDEX IF NOT EXISTS idx_api_usage_owner ON api_usage (owner_token_hash);
