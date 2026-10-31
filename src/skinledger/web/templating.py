"""Shared Jinja2 environment for full pages and HTMX fragments."""

from datetime import datetime
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
    privacy_lead=copy.PRIVACY_LEAD,
    privacy_note=copy.PRIVACY_NOTE,
    capture_kit_timeout=copy.CAPTURE_KIT_TIMEOUT,
    capture_kit_timeout_no_upload=copy.CAPTURE_KIT_TIMEOUT_NO_UPLOAD,
    capture_api_timeout=copy.CAPTURE_API_TIMEOUT,
    capture_network_error=copy.CAPTURE_NETWORK_ERROR,
    capture_lost_track=copy.CAPTURE_LOST_TRACK,
    capture_uploading=copy.CAPTURE_UPLOADING,
    capture_retry=copy.CAPTURE_RETRY,
    capture_tab_note=copy.CAPTURE_TAB_NOTE,
    capture_upload_note=copy.CAPTURE_UPLOAD_NOTE,
    capture_tips_title=copy.CAPTURE_TIPS_TITLE,
    upload_tips_title=copy.UPLOAD_TIPS_TITLE,
    upload_tip=copy.UPLOAD_TIP,
    product_target_count=copy.PRODUCT_TARGET_COUNT,
    product_targets_title=copy.PRODUCT_TARGETS_TITLE,
    product_date_note=copy.PRODUCT_DATE_NOTE,
    product_add_title=copy.PRODUCT_ADD_TITLE,
    capture_tips=copy.CAPTURE_TIPS,
    guidance_order=",".join(copy.GUIDANCE_ORDER),
    guidance_chips=copy.GUIDANCE_CHIPS,
    guidance_initial=copy.GUIDANCE_INITIAL,
    guidance_toosmall=copy.GUIDANCE_TOOSMALL,
    guidance_outofboundary=copy.GUIDANCE_OUTOFBOUNDARY,
    guidance_lighting=copy.GUIDANCE_LIGHTING,
    guidance_frontal=copy.GUIDANCE_FRONTAL,
    guidance_all_good=copy.GUIDANCE_ALL_GOOD,
    capture_fallback_text=copy.CAPTURE_FALLBACK_TEXT,
    capture_fallback_ms=copy.CAPTURE_FALLBACK_SECONDS * 1000,
    baseline_done=copy.BASELINE_DONE,
    timeline_product_key=copy.TIMELINE_PRODUCT_KEY,
    timeline_numbers=copy.TIMELINE_NUMBERS,
    timeline_show_fewer=copy.TIMELINE_SHOW_FEWER,
    timeline_shown_note=copy.TIMELINE_SHOWN_NOTE,
    timeline_band_prefix=copy.TIMELINE_BAND_PREFIX,
    timeline_summary_latest=copy.TIMELINE_SUMMARY_LATEST,
    timeline_noscript=copy.TIMELINE_NOSCRIPT,
    timeline_no_points=copy.TIMELINE_NO_POINTS,
    features=FEATURES,
    verdict_title_prefix=copy.VERDICT_TITLE_PREFIX,
    verdict_simulated_banner=copy.VERDICT_SIMULATED_BANNER,
    verdict_sample_banner=copy.VERDICT_SAMPLE_BANNER,
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
    try_sample_link=copy.TRY_SAMPLE_LINK,
    try_invite_hint=copy.TRY_INVITE_HINT,
    sample_profile_banner=copy.SAMPLE_PROFILE_BANNER,
    home_sample_link=copy.HOME_SAMPLE_LINK,
    home_sample_title=copy.HOME_SAMPLE_TITLE,
    demo_read_only=copy.DEMO_READ_ONLY,
    try_demo_link=copy.TRY_DEMO_LINK,
    demo_title=copy.DEMO_TITLE,
    demo_intro=copy.DEMO_INTRO,
    demo_sample_link=copy.DEMO_SAMPLE_LINK,
    demo_try_link=copy.DEMO_TRY_LINK,
    demo_invite_note=copy.DEMO_INVITE_NOTE,
    demo_privacy_note=copy.DEMO_PRIVACY_NOTE,
    footer_demo_link=copy.FOOTER_DEMO_LINK,
    footer_privacy=copy.PRIVACY_TITLE,
    admin_usage_title=copy.ADMIN_USAGE_TITLE,
    admin_visitor_analyses_today=copy.ADMIN_VISITOR_ANALYSES_TODAY,
    admin_visitor_analyses_total=copy.ADMIN_VISITOR_ANALYSES_TOTAL,
    admin_visitor_units_today=copy.ADMIN_VISITOR_UNITS_TODAY,
    admin_visitor_units_total=copy.ADMIN_VISITOR_UNITS_TOTAL,
    admin_units=copy.ADMIN_UNITS,
    admin_analyses_left=copy.ADMIN_ANALYSES_LEFT,
    admin_daily_cap=copy.ADMIN_DAILY_CAP,
    admin_total_cap=copy.ADMIN_TOTAL_CAP,
    admin_per_person_cap=copy.ADMIN_PER_PERSON_CAP,
    admin_allow_upload=copy.ADMIN_ALLOW_UPLOAD,
    admin_balance=copy.ADMIN_BALANCE,
    admin_files_outside=copy.ADMIN_FILES_OUTSIDE,
    admin_rejected_title=copy.ADMIN_REJECTED_TITLE,
    admin_rejected_none=copy.ADMIN_REJECTED_NONE,
    admin_unavailable=copy.ADMIN_UNAVAILABLE,
    routine_title=copy.ROUTINE_TITLE,
    routine_lowest_title=copy.ROUTINE_LOWEST_TITLE,
    routine_am_title=copy.ROUTINE_AM_TITLE,
    routine_pm_title=copy.ROUTINE_PM_TITLE,
    routine_week_title=copy.ROUTINE_WEEK_TITLE,
    routine_shopping_title=copy.ROUTINE_SHOPPING_TITLE,
    routine_copy_button=copy.ROUTINE_COPY_BUTTON,
    routine_copied=copy.ROUTINE_COPIED,
    routine_copy_empty=copy.ROUTINE_COPY_EMPTY,
    routine_footer=copy.ROUTINE_FOOTER,
    routine_no_capture=copy.ROUTINE_NO_CAPTURE,
    routine_take_capture=copy.ROUTINE_TAKE_CAPTURE,
    routine_data_prefix=copy.ROUTINE_DATA_PREFIX,
    routine_keep_using=copy.ROUTINE_KEEP_USING,
    routine_no_shopping=copy.ROUTINE_NO_SHOPPING,
    routine_shopping_note=copy.ROUTINE_SHOPPING_NOTE,
    routine_col_aspect=copy.ROUTINE_COL_ASPECT,
    routine_col_score=copy.ROUTINE_COL_SCORE,
    routine_col_band=copy.ROUTINE_COL_BAND,
    routine_day_am=copy.ROUTINE_DAY_AM,
    routine_day_pm=copy.ROUTINE_DAY_PM,
    routine_always=copy.ROUTINE_ALWAYS,
)

_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def short_date(value: object) -> str:
    """A compact date for tables and keys: 'Oct 4'. Falls back to the raw text."""
    text = str(value or "")
    try:
        moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return text[:10]
    return f"{_MONTHS[moment.month - 1]} {moment.day}"


templates.env.filters["short_date"] = short_date
