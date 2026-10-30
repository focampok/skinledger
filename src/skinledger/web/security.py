"""Security headers for every response (P15/P15a/P15c).

The strict policy has no 'unsafe-inline' for scripts and no 'unsafe-eval': every
script is an external file under /static/ or the Camera Kit SDK. The Kit origins
live in one config constant so a browser-console CSP report has a single place to
update.

P15c: the guided capture page is the only page that loads the Kit, and the Kit
needs a looser policy (it evaluates strings as JS, compiles WebAssembly, and pulls
its own stylesheets, fonts and images from third-party origins). That policy is
built by `capture_content_security_policy()` and selected per request by
`is_capture_path()`, so every other page keeps the strict one.
"""

from __future__ import annotations

import json
import re

from skinledger.config import CAMERA_KIT_ORIGINS

REPORT_GROUP = "csp-endpoint"
REPORT_PATH = "/csp-report"
REPORT_MAX_AGE = 10886400

# The only route that renders capture.html, which loads the Camera Kit SDK.
CAPTURE_PATH_PATTERN = re.compile(r"\A/people/\d+/capture/?\Z")

# Third-party origins the Kit serves its own CSS, webfonts and images from (P15c).
CAPTURE_STYLE_ORIGINS: tuple[str, ...] = (
    "https://fonts.googleapis.com",
    "https://cdnjs.cloudflare.com",
)
CAPTURE_FONT_ORIGINS: tuple[str, ...] = (
    "https://fonts.gstatic.com",
    "https://cdnjs.cloudflare.com",
)


def is_capture_path(path: str) -> bool:
    """True only for the guided capture page, the one route that loads the Kit."""
    return CAPTURE_PATH_PATTERN.match(path) is not None


def content_security_policy() -> str:
    """Strict policy for every page except the guided capture page."""
    kit = " ".join(CAMERA_KIT_ORIGINS)
    # 'wasm-unsafe-eval' is intentionally absent here. Only the capture page,
    # which runs the Kit, needs it; see capture_content_security_policy().
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
        "object-src 'none'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        f"report-uri {REPORT_PATH}; "
        f"report-to {REPORT_GROUP}"
    )


def capture_content_security_policy() -> str:
    """Strict policy plus exactly what the Camera Kit needs, for the capture page only.

    The Kit evaluates strings as JS (1000+ violations under report-only), compiles
    WebAssembly, and loads its stylesheets, webfonts and images from third-party
    origins. Scripts still forbid 'unsafe-inline': every script stays an external
    file. Reporting directives, frame-ancestors, object-src and base-uri are the
    same as on the strict policy.
    """
    kit = " ".join(CAMERA_KIT_ORIGINS)
    style = " ".join(CAPTURE_STYLE_ORIGINS)
    font = " ".join(CAPTURE_FONT_ORIGINS)
    return (
        "default-src 'self'; "
        f"script-src 'self' {kit} 'unsafe-eval' 'wasm-unsafe-eval'; "
        f"style-src 'self' 'unsafe-inline' {style}; "
        f"font-src 'self' data: {font} {kit}; "
        f"img-src 'self' blob: data: https: {kit}; "
        "media-src 'self' blob:; "
        f"connect-src 'self' {kit} blob: data:; "
        "worker-src 'self' blob:; "
        f"frame-src 'self' {kit}; "
        "frame-ancestors 'none'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        f"report-uri {REPORT_PATH}; "
        f"report-to {REPORT_GROUP}"
    )


def security_headers(
    *, report_only: bool = False, report_url: str = REPORT_PATH, capture: bool = False
) -> dict[str, str]:
    """The CSP (enforcing or report-only) plus the reporting and hardening headers.

    `capture` selects the relaxed Kit policy; callers pass it only for the capture page.
    """
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
    policy = (
        capture_content_security_policy()
        if capture
        else content_security_policy()
    )
    return {
        csp_header: policy,
        "Report-To": report_to,
        "Permissions-Policy": "camera=(self)",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Referrer-Policy": "same-origin",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
    }
