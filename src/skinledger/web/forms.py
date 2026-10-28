"""Small urlencoded form parser; never multipart, so no python-multipart is needed."""

from __future__ import annotations

from urllib.parse import parse_qs

from fastapi import Request

MAX_FORM_BYTES = 64 * 1024


async def read_urlencoded_form(request: Request) -> dict[str, str]:
    """Read a small application/x-www-form-urlencoded body into a dict."""
    content_type = request.headers.get("content-type", "")
    if "application/x-www-form-urlencoded" not in content_type:
        return {}
    body = await request.body()
    if len(body) > MAX_FORM_BYTES:
        return {}
    parsed = parse_qs(body.decode("utf-8", "replace"), keep_blank_values=True)
    return {key: values[-1] for key, values in parsed.items()}
