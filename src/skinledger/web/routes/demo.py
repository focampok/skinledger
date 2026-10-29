"""Judges' demo page: explains the public sample profile and /try (P15)."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from skinledger.web.demo import sample_person_id
from skinledger.web.templating import templates

router = APIRouter()


@router.get("/demo", response_class=HTMLResponse)
async def demo_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "demo.html",
        {"demo_person_id": sample_person_id()},
    )
