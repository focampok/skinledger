"""Product copy constants shared by templates and routes."""

DISCLAIMER = (
    "Cosmetic skin insights, not a medical diagnosis. Scores are AI estimates and vary with "
    "lighting. See a dermatologist for persistent acne, changing moles, rashes or pain."
)

POWERED_BY = "Powered by YouCam API"

ATTESTATION = "This is my own face and I am 18 or older."

LIMIT_REACHED = (
    "Demo limit reached — thanks for trying SkinLedger! Explore the sample profile instead."
)

CONSENT_REQUIRED = "Please accept the consent first."

ATTESTATION_REQUIRED = f"Please confirm: {ATTESTATION}"

INVITE_REQUIRED = "An invite code is required to run an analysis."

ATTEMPT_FREE = "This attempt didn't count toward your limit."

UPLOAD_DISABLED = "Photo upload is currently unavailable. Use the guided camera instead."

TRY_AGAIN_NO_UNITS = "Please try again. No units were charged."

TASK_EXPIRED = "This analysis expired. No units were charged."

CONSENT_VERSION = "consent-v2"

INVALID_INVITE = "That invite code isn't valid."

TOO_MANY_INVITE_ATTEMPTS = "Too many attempts. Try again in an hour."

CONSENT_BOXES_REQUIRED = "Please tick both boxes to continue."

NAME_REQUIRED = "Please enter a display name."

DELETE_CONFIRM_MISMATCH = "Type the profile name exactly to confirm."

DEMO_READ_ONLY = "This sample profile is read-only."

DELETED_MESSAGE = (
    "Deleted from SkinLedger. Your photo was never stored here. To ask YouCam to "
    "delete the uploaded photo sooner, contact Perfect Corp (YouCam API support)."
)

PRIVACY_NOTE = (
    "Your photo is sent to the YouCam API (Perfect Corp) for analysis and is never stored "
    "by SkinLedger. YouCam may keep it for up to 30 days. See Privacy."
)

UPLOAD_TIP = (
    "Use a recent, well-lit, front-facing photo of your own face, no filters. For weekly "
    "tracking, use the guided capture — same light, same distance."
)

BASELINE_DONE = (
    "That's how much your score moves on its own — SkinLedger only counts changes bigger "
    "than this."
)

BASELINE_INTRO = (
    "Estimated from 2 captures on day 1. Changes smaller than the band are treated as noise. "
    "Unstable aspects are shown but not used for product verdicts."
)

BASELINE_UNSTABLE_HINT = (
    "Some scores move a lot between back-to-back photos. Same place, same light and same "
    "distance keep the band tight."
)

NO_BAND_YET = "Take 2 baseline captures first."

TIMELINE_TITLE = "Your skin, measured against your own noise"

TIMELINE_BAND_LEGEND = (
    "Shaded band = your day-1 measurement noise. Only changes outside it count."
)

TIMELINE_UNSTABLE_CHIP = "Unstable for your setup"

TIMELINE_UNSTABLE_NOTE = (
    "This score moved more than 10 points between your two day-1 captures, so "
    "SkinLedger won't use it for verdicts."
)

PRODUCT_NAME_PLACEHOLDER = "e.g. Niacinamide serum"

PRODUCT_NAME_NOTE = "Use a generic name; no brand needed"

PRODUCT_UNSTABLE_HINT = (
    "Unstable for your setup — it won't count in this product's verdict."
)

PRODUCT_NAME_REQUIRED = "Please enter a product name."

PRODUCT_NAME_TOO_LONG = "Please use 80 characters or fewer."

PRODUCT_CATEGORY_INVALID = "Choose one of the listed categories."

PRODUCT_DATE_INVALID = "Use dates like 2026-10-29."

PRODUCT_DATE_ORDER = "End date can't be before the start date."

PRODUCT_TARGETS_REQUIRED = "Pick 1 to 4 target aspects."

PRODUCT_TOO_MANY_TARGETS = "Choose up to 4 target aspects."

PRODUCT_UNKNOWN_TARGET = "Unknown target aspect. Choose from the 15 listed aspects."
