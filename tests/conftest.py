"""Shared test setup: an autouse fixture keeps every test out of the repository `./logs`."""

from __future__ import annotations

import pytest

from skinledger import config, logs


@pytest.fixture(scope="session")
def log_fallback_dir(tmp_path_factory):
    """A session directory the file handler can stay on between tests."""
    return tmp_path_factory.mktemp("log-fallback")


@pytest.fixture(autouse=True)
def isolate_log_dir(tmp_path, log_fallback_dir, monkeypatch):
    """Point LOG_DIR at a temp directory before a test can emit an event.

    `skinledger.web.app` configures the file handler when it is imported, so the
    process may already hold ./logs/skinledger.jsonl open. Reconfiguring here moves
    the handler off it before the test body runs.
    """
    monkeypatch.setattr(config.settings, "log_dir", tmp_path / "logs")
    logs.configure_logging()
    yield
    # Restoring LOG_DIR to ./logs would reopen the repository file, so leave the
    # handler on a session directory; monkeypatch puts the setting itself back.
    monkeypatch.setattr(config.settings, "log_dir", log_fallback_dir)
    logs.configure_logging()
