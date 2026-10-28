"""Shared Jinja2 environment for full pages and HTMX fragments."""

from pathlib import Path

from fastapi.templating import Jinja2Templates

from skinledger import copy

WEB_DIR = Path(__file__).resolve().parent

templates = Jinja2Templates(directory=str(WEB_DIR / "templates"))
templates.env.globals.update(
    disclaimer=copy.DISCLAIMER,
    powered_by=copy.POWERED_BY,
    attestation=copy.ATTESTATION,
    privacy_note=copy.PRIVACY_NOTE,
    upload_tip=copy.UPLOAD_TIP,
    baseline_done=copy.BASELINE_DONE,
)
