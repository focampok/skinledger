"""Automated copy audit: no medical language, no brands, disclaimer present (P13).

The audit is deliberately blunt: it scans every template, static JS file and the
README, plus the routine/verdict output strings, and reports ``file:line``.
The exact DISCLAIMER and the allowed YouCam contexts are the only exceptions.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from skinledger import copy

BANNED_STEMS = ("diagnos", "treat", "cure", "disease", "prescription", "medication")

DEFAULT_BANNED_BRANDS = (
    "cerave",
    "cetaphil",
    "neutrogena",
    "la roche",
    "la-roche",
    "the ordinary",
    "paula's choice",
    "paulas choice",
    "olay",
    "nivea",
    "clinique",
    "estee lauder",
    "l'oreal",
    "loreal",
    "kiehl",
    "avene",
    "eucerin",
    "bioderma",
    "biore",
    "garnier",
    "cosrx",
    "innisfree",
    "laneige",
    "drunk elephant",
    "glossier",
    "fenty",
    "sephora",
)

POWERED_BY = "Powered by YouCam API"
YOUCAM = "YouCam"
YOUCAM_ALLOWED_FILES = frozenset({"consent.html", "privacy.html"})


@dataclass(frozen=True)
class Finding:
    file: str
    line: int
    word: str
    text: str

    def __str__(self) -> str:
        excerpt = self.text.strip()[:140]
        return f"{self.file}:{self.line}: {self.word}: {excerpt}"


def _stem_pattern(stem: str) -> re.Pattern[str]:
    return re.compile(r"\b" + re.escape(stem) + r"\w*", re.IGNORECASE)


def _brand_pattern(brand: str) -> re.Pattern[str]:
    return re.compile(r"\b" + re.escape(brand) + r"\b", re.IGNORECASE)


_BANNED_PATTERNS = tuple((stem, _stem_pattern(stem)) for stem in BANNED_STEMS)


def scan_text(
    text: str,
    *,
    file: str = "<text>",
    brands: Iterable[str] = (),
    allow_youcam: bool = False,
) -> list[Finding]:
    """Find banned stems, brands and disallowed YouCam mentions with line numbers."""
    brand_list = tuple(dict.fromkeys((*DEFAULT_BANNED_BRANDS, *brands)))
    brand_patterns = tuple((brand, _brand_pattern(brand)) for brand in brand_list)
    findings: list[Finding] = []
    for number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.replace(copy.DISCLAIMER, "")
        for stem, pattern in _BANNED_PATTERNS:
            if pattern.search(line):
                findings.append(Finding(file, number, stem, raw_line))
        for brand, pattern in brand_patterns:
            if pattern.search(line):
                findings.append(Finding(file, number, brand, raw_line))
        if not allow_youcam and YOUCAM in line:
            stripped = line.replace(POWERED_BY, "")
            if YOUCAM in stripped:
                findings.append(Finding(file, number, YOUCAM, raw_line))
    return findings


def scan_file(
    path: Path, *, brands: Iterable[str] = (), allow_youcam: bool | None = None
) -> list[Finding]:
    if allow_youcam is None:
        allow_youcam = path.name in YOUCAM_ALLOWED_FILES
    return scan_text(
        path.read_text(encoding="utf-8"),
        file=str(path),
        brands=brands,
        allow_youcam=allow_youcam,
    )


def audit_repo(root: Path, *, brands: Iterable[str] = ()) -> list[Finding]:
    """Scan templates, static JS and the README; returns every finding."""
    findings: list[Finding] = []
    for path in sorted((root / "src/skinledger/web/templates").glob("*.html")):
        findings.extend(scan_file(path, brands=brands))
    for path in sorted((root / "src/skinledger/web/static").glob("*.js")):
        findings.extend(scan_file(path, brands=brands))
    findings.extend(
        scan_file(root / "README.md", brands=brands, allow_youcam=True)
    )
    return findings


def format_findings(findings: Iterable[Finding]) -> str:
    return "\n".join(str(finding) for finding in findings)
