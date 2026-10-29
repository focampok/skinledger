"""Security headers for every response (P15).

The script policy has no 'unsafe-inline': every script is an external file under
/static/ or the Camera Kit SDK. The Kit origins live in one config constant so a
browser-console CSP report has a single place to update.
"""

from __future__ import annotations

from skinledger.config import CAMERA_KIT_ORIGINS


def content_security_policy() -> str:
    kit = " ".join(CAMERA_KIT_ORIGINS)
    return (
        "default-src 'self'; "
        f"script-src 'self' {kit}; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' blob: data:; "
        "media-src 'self' blob:; "
        f"connect-src 'self' {kit}; "
        "worker-src 'self' blob:; "
        f"frame-src 'self' {kit}; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )


SECURITY_HEADERS: dict[str, str] = {
    "Content-Security-Policy": content_security_policy(),
    "Permissions-Policy": "camera=(self)",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Referrer-Policy": "same-origin",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
}
