"""Shared Jinja2 environment for full pages and HTMX fragments."""

from pathlib import Path

from fastapi.templating import Jinja2Templates

from skinledger import copy
from skinledger.features import FEATURES

WEB_DIR = Path(__file__).resolve().parent

templates = Jinja2Templates(directory=str(WEB_DIR / "templates"))
templates.env.globals.update(
    disclaimer=copy.DISCLAIMER,
    powered_by=copy.POWERED_BY,
    attestation=copy.ATTESTATION,
    privacy_note=copy.PRIVACY_NOTE,
    upload_tip=copy.UPLOAD_TIP,
    baseline_done=copy.BASELINE_DONE,
    features=FEATURES,
    verdict_title_prefix=copy.VERDICT_TITLE_PREFIX,
    verdict_simulated_banner=copy.VERDICT_SIMULATED_BANNER,
    verdict_masks_real_only=copy.VERDICT_MASKS_REAL_ONLY,
    verdict_no_masks=copy.VERDICT_NO_MASKS,
    verdict_unstable_not_used=copy.VERDICT_UNSTABLE_NOT_USED,
    verdict_take_checkin=copy.VERDICT_TAKE_CHECKIN,
    verdict_targets_title=copy.VERDICT_TARGETS_TITLE,
    verdict_top_changes_title=copy.VERDICT_TOP_CHANGES_TITLE,
    verdict_masks_title=copy.VERDICT_MASKS_TITLE,
    verdict_col_aspect=copy.VERDICT_COL_ASPECT,
    verdict_col_baseline=copy.VERDICT_COL_BASELINE,
    verdict_col_checkin=copy.VERDICT_COL_CHECKIN,
    verdict_col_change=copy.VERDICT_COL_CHANGE,
    verdict_col_band=copy.VERDICT_COL_BAND,
    verdict_col_outside=copy.VERDICT_COL_OUTSIDE,
    verdict_before=copy.VERDICT_BEFORE,
    verdict_after=copy.VERDICT_AFTER,
    verdict_mask_before_alt=copy.VERDICT_MASK_BEFORE_ALT,
    verdict_mask_after_alt=copy.VERDICT_MASK_AFTER_ALT,
    home_active_title=copy.HOME_ACTIVE_TITLE,
    home_next_checkin=copy.HOME_NEXT_CHECKIN,
    home_both_passed=copy.HOME_BOTH_PASSED,
    home_no_active=copy.HOME_NO_ACTIVE,
)
