"""Security headers for every response (P15/P15a).

The script policy has no 'unsafe-inline': every script is an external file under
/static/ or the Camera Kit SDK. The Kit origins live in one config constant so a
browser-console CSP report has a single place to update.
"""

from __future__ import annotations

import json

from skinledger.config import CAMERA_KIT_ORIGINS

REPORT_GROUP = "csp-endpoint"
REPORT_PATH = "/csp-report"
REPORT_MAX_AGE = 10886400


def content_security_policy() -> str:
    kit = " ".join(CAMERA_KIT_ORIGINS)
    # 'wasm-unsafe-eval' is intentionally absent. The Camera Kit SDK may need it
    # for WebAssembly; add it only after csp.violation logs confirm it is required.
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
        "form-action 'self'; "
        f"report-uri {REPORT_PATH}; "
        f"report-to {REPORT_GROUP}"
    )


def security_headers(
    *, report_only: bool = False, report_url: str = REPORT_PATH
) -> dict[str, str]:
    """The CSP (enforcing or report-only) plus the reporting and hardening headers."""
    csp_header = (
        "Content-Security-Policy-Report-Only"
        if report_only
        else "Content-Security-Policy"
    )
    report_to = json.dumps(
        {
            "group": REPORT_GROUP,
            "max_age": REPORT_MAX_AGE,
            "endpoints": [{"url": report_url}],
        },
        separators=(",", ":"),
    )
    return {
        csp_header: content_security_policy(),
        "Report-To": report_to,
        "Permissions-Policy": "camera=(self)",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Referrer-Policy": "same-origin",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
    }
