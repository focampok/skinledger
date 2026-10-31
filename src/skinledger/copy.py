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
    "Deleted from SkinLedger. Your photo was never stored here. To ask for the uploaded "
    "photo to be deleted sooner, contact YouCam API support (Perfect Corp)."
)

PRIVACY_LEAD = "We never store your photo."

PRIVACY_NOTE = (
    "Your photo is sent to the YouCam API (Perfect Corp) for analysis. "
    "YouCam may keep it for up to 30 days."
)

# P16b-3: capture page status and recovery copy. The browser applies these
# strings; the wording lives here so the tests can check it without a browser.
CAPTURE_KIT_TIMEOUT = "The camera is taking too long. Upload a selfie instead."
CAPTURE_KIT_TIMEOUT_NO_UPLOAD = "The camera is taking too long. Try again later."
CAPTURE_API_TIMEOUT = "This is taking too long. Check your connection and try again."
CAPTURE_NETWORK_ERROR = "We couldn't reach SkinLedger. Check your connection and try again."
CAPTURE_LOST_TRACK = (
    "We lost track of this analysis. Check your connection and try again."
)
CAPTURE_UPLOADING = "Uploading…"
CAPTURE_RETRY = "Retry"
CAPTURE_TAB_NOTE = (
    "Guided capture (recommended for tracking) keeps light and distance the same for each check-in."
)
CAPTURE_UPLOAD_NOTE = (
    "Quick try: upload a photo from your device. Lighting varies, so use it for a first look."
)
CAPTURE_TIPS_TITLE = "Tips for a good capture"
UPLOAD_TIPS_TITLE = "Before you upload"

UPLOAD_TIP = (
    "Use a recent, well-lit, front-facing photo of your own face, no filters."
)

# P16a: guided-capture guidance. One instruction is shown at a time, chosen in
# GUIDANCE_ORDER; the browser only applies these strings, so the wording and the
# priority live here and in the tests.
CAPTURE_TIPS = (
    "Light in front of you, not behind you.",
    "Phone at eye level, an arm's length away.",
    "Glasses off and hair off your forehead.",
)

GUIDANCE_INITIAL = "Point the camera at your face"
GUIDANCE_TOOSMALL = "Move closer: fill the oval with your face"
GUIDANCE_OUTOFBOUNDARY = "Center your face in the oval"
GUIDANCE_LIGHTING = "Face a window or lamp; avoid light from behind"
GUIDANCE_FRONTAL = "Look straight at the camera, chin level"
GUIDANCE_ALL_GOOD = "Hold still..."

# Priority: position before lighting before frontal.
GUIDANCE_ORDER = ("position", "lighting", "frontal")

GUIDANCE_CHIPS = (
    ("position", "Position"),
    ("lighting", "Light"),
    ("frontal", "Angle"),
)

# After this long without all three good, offer the upload fallback.
CAPTURE_FALLBACK_SECONDS = 45
CAPTURE_FALLBACK_TEXT = "Having trouble? Upload a selfie instead"

BASELINE_DONE = (
    "That's how much your score moves on its own — SkinLedger only counts changes bigger "
    "than this."
)

BASELINE_INTRO = (
    "Estimated from 2 captures on day 1. Changes smaller than the band are counted as noise. "
    "Unstable aspects are shown but not used for product verdicts."
)

BASELINE_UNSTABLE_HINT = (
    "Some scores move a lot between back-to-back photos. Same place, same light and same "
    "distance keep the band tight."
)

NO_BAND_YET = "Take 2 baseline captures first."

TIMELINE_TITLE = "Your skin, measured against your own noise"

TIMELINE_PRODUCT_KEY = "Product starts"
TIMELINE_NUMBERS = "Numbers"
TIMELINE_SHOW_ALL = "Show all {count} aspects"
TIMELINE_SHOW_FEWER = "Show fewer"
TIMELINE_SHOWN_NOTE = "Product targets first."
TIMELINE_BAND_PREFIX = "Noise band"
TIMELINE_SUMMARY_LATEST = "Latest check-in"
TIMELINE_NOSCRIPT = "Charts need JavaScript. Open Numbers in each card for the values."
TIMELINE_NO_POINTS = "No captures yet."

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
    "Greyed aspects are unstable for this person's setup and won't count in the verdict."
)

PRODUCT_TARGET_COUNT = "{count} of {max} selected"
PRODUCT_TARGETS_TITLE = "Target aspects (1 to 4)"
PRODUCT_DATE_NOTE = "Saved as YYYY-MM-DD."
PRODUCT_ADD_TITLE = "Add a product"

PRODUCT_NAME_REQUIRED = "Please enter a product name."

PRODUCT_NAME_TOO_LONG = "Please use 80 characters or fewer."

PRODUCT_CATEGORY_INVALID = "Choose one of the listed categories."

PRODUCT_DATE_INVALID = "Use dates like 2026-10-29."

PRODUCT_DATE_ORDER = "End date can't be before the start date."

PRODUCT_TARGETS_REQUIRED = "Pick 1 to 4 target aspects."

PRODUCT_TOO_MANY_TARGETS = "Choose up to 4 target aspects."

PRODUCT_UNKNOWN_TARGET = "Unknown target aspect. Choose from the 15 listed aspects."

# -- P11 verdict screen and home cards ---------------------------------------

VERDICT_OUTCOME_LABELS = {
    "keep": "Keep",
    "no_change": "No measurable change",
    "worse": "Worse",
    "too_early": "Too early",
    "no_band": "No verdict yet",
    "need_checkin": "Check-in needed",
}


def verdict_outcome_label(outcome: str) -> str:
    return VERDICT_OUTCOME_LABELS.get(outcome, outcome)


VERDICT_TITLE_PREFIX = "Verdict for"

VERDICT_SIMULATED_BANNER = "Demo: day 14/28 check-ins are SIMULATED. Day 1 is real."

VERDICT_MASKS_REAL_ONLY = "Masks are only shown for real captures."

VERDICT_NO_MASKS = "No masks are stored for these captures."

VERDICT_UNSTABLE_NOT_USED = "Unstable, not used"

VERDICT_TAKE_CHECKIN = "Take check-in now"

VERDICT_TARGETS_TITLE = "Target aspects"

VERDICT_TOP_CHANGES_TITLE = "Biggest changes"

VERDICT_MASKS_TITLE = "Before and after masks"

VERDICT_COL_ASPECT = "Target aspect"

VERDICT_COL_BASELINE = "Baseline"

VERDICT_COL_CHECKIN = "Check-in"

VERDICT_COL_CHANGE = "Change"

VERDICT_COL_BAND = "Noise band"

VERDICT_COL_OUTSIDE = "Outside noise?"

VERDICT_DAY_14 = "Day 14"

VERDICT_DAY_28 = "Day 28"

VERDICT_OUTSIDE_NOISE = "Outside noise"

VERDICT_WITHIN_NOISE = "Within noise"

VERDICT_NO_BAND_CELL = "No band"

VERDICT_PENDING_CELL = "Check-in not taken"

VERDICT_NO_SCORE = "No score"

VERDICT_BEFORE = "Before"

VERDICT_AFTER = "After"

VERDICT_MASK_BEFORE_ALT = "Before mask for"

VERDICT_MASK_AFTER_ALT = "After mask for"

HOME_ACTIVE_TITLE = "Your active products"

HOME_NEXT_CHECKIN = "Next check-in"

HOME_BOTH_PASSED = "Both check-in windows have passed."

HOME_NO_ACTIVE = "No active products yet."

VERDICT_SAMPLE_BANNER = "Sample data for testing, not a real result."

SAMPLE_PROFILE_BANNER = "Sample profile: all data is SIMULATED."

TRY_SAMPLE_LINK = "Open the sample profile (all data is SIMULATED)"
TRY_INVITE_HINT = "From the Devpost testing instructions."

TRY_DEMO_LINK = "About the demo"

HOME_SAMPLE_LINK = "Open the sample profile (SIMULATED)"
HOME_SAMPLE_TITLE = "Sample profile products"

HOME_OUTCOME_DETAILS = {
    "keep": "The change is bigger than your noise band.",
    "no_change": "Reconsider before rebuying.",
    "worse": "Pause and look at what changed.",
    "too_early": "Check back on day 14.",
    "no_band": "Take 2 baseline captures first.",
    "need_checkin": "Take the next check-in.",
}


def home_outcome_detail(outcome: str) -> str:
    return HOME_OUTCOME_DETAILS.get(outcome, "")

DEMO_TITLE = "SkinLedger demo"

DEMO_INTRO = (
    "The public sample profile is Sample user (SIMULATED). All its data is "
    "SIMULATED, so anyone can browse it without an invite code."
)

DEMO_SAMPLE_LINK = "Open the sample profile"

DEMO_TRY_LINK = "Try it with your own face"

DEMO_INVITE_NOTE = (
    "An invite code is required to analyze your own face; it is in the Devpost "
    "testing instructions. 2 analyses per person."
)

DEMO_PRIVACY_NOTE = "Your photo is never stored."

FOOTER_DEMO_LINK = "Demo"

# -- Admin usage page ---------------------------------------------------------

ADMIN_USAGE_TITLE = "Admin usage"

ADMIN_VISITOR_ANALYSES_TODAY = "Visitor analyses today"

ADMIN_VISITOR_ANALYSES_TOTAL = "Visitor analyses since deploy"

ADMIN_VISITOR_UNITS_TODAY = "Visitor units today"

ADMIN_VISITOR_UNITS_TOTAL = "Visitor units since deploy"

ADMIN_UNITS = "Admin units (your own analyses)"

ADMIN_ANALYSES_LEFT = "Analyses left in the visitor pool"

ADMIN_DAILY_CAP = "Daily unit cap"

ADMIN_TOTAL_CAP = "Total unit cap"

ADMIN_PER_PERSON_CAP = "Analyses per person"

ADMIN_ALLOW_UPLOAD = "Photo upload allowed"

ADMIN_BALANCE = "YouCam balance"

ADMIN_FILES_OUTSIDE = "Files outside masks/ in DATA_DIR (must be 0)"

ADMIN_REJECTED_TITLE = "Rejected (0-unit) attempts by error code"

ADMIN_REJECTED_NONE = "None."

ADMIN_UNAVAILABLE = "unavailable"

# -- P12 routine and shopping list -------------------------------------------

ROUTINE_TITLE = "Your AM/PM routine"

ROUTINE_LOWEST_TITLE = "Your 3 lowest aspects"

ROUTINE_AM_TITLE = "Morning (AM)"

ROUTINE_PM_TITLE = "Evening (PM)"

ROUTINE_WEEK_TITLE = "Your week"

ROUTINE_SHOPPING_TITLE = "Shopping list"

ROUTINE_COPY_BUTTON = "Copy list"

ROUTINE_COPIED = "Copied"

ROUTINE_COPY_EMPTY = "Select at least one item."

ROUTINE_FOOTER = "General cosmetic heuristics, not personal medical advice."

ROUTINE_ONE_CAPTURE = (
    "Based on one capture; take your 2 baseline captures for a steadier routine."
)

ROUTINE_FEW_STABLE = (
    "Fewer than 3 stable aspects are available; the routine uses the ones that are."
)

ROUTINE_ALL_UNSTABLE = (
    "All your aspects are too noisy in your setup to build a specific routine."
)

ROUTINE_UNSTABLE_EXCLUDED = "Unstable aspects are excluded from the lowest 3."

ROUTINE_NO_CAPTURE = "Take a capture first."

ROUTINE_TAKE_CAPTURE = "Take a capture"

ROUTINE_DATA_PREFIX = "Data"

ROUTINE_KEEP_USING = "Keep using"

ROUTINE_NO_SHOPPING = (
    "Nothing to add: your active products already cover these categories."
)

ROUTINE_SHOPPING_NOTE = "Generic categories only; no brands."

ROUTINE_COL_ASPECT = "Aspect"

ROUTINE_COL_SCORE = "Score"

ROUTINE_COL_BAND = "Noise band"

ROUTINE_DAY_AM = "AM"

ROUTINE_DAY_PM = "PM"

ROUTINE_ALWAYS = "Every day"

ROUTINE_DAYS = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)

# Generic ingredient categories from plan §13; no brands and no doses.
ROUTINE_ITEM_NIACINAMIDE = "Niacinamide serum"

ROUTINE_ITEM_GEL = "Lightweight gel moisturizer"

ROUTINE_ITEM_CERAMIDE = "Ceramide or hyaluronic acid moisturizer"

ROUTINE_ITEM_SPF = "Broad-spectrum SPF 30+"

ROUTINE_ITEM_VITAMIN_C = "Vitamin C serum"

ROUTINE_ITEM_FRAGRANCE_FREE = "Fragrance-free gentle cleanser"

ROUTINE_ITEM_SOOTHING = "Soothing moisturizer"

ROUTINE_ITEM_AVOID_TONERS = "Avoid alcohol-heavy toners"

ROUTINE_EYE_NOTE = "Sleep and hydration also help."

ROUTINE_ITEM_BHA = "Salicylic acid (BHA) cleanser"

ROUTINE_ITEM_AHA = "Gentle exfoliant (AHA/PHA)"

ROUTINE_ITEM_RETINOL = "Retinol serum"

ROUTINE_ITEM_CAFFEINE = "Caffeine eye cream"

ROUTINE_ITEM_CLEANSER = "Gentle cleanser"

ROUTINE_ITEM_MOISTURIZER = "Moisturizer"

# -- Privacy page (P13 audit prerequisite; full P15 page can extend it) ------

PRIVACY_TITLE = "Privacy"

PRIVACY_TEXT = (
    "SkinLedger is a hackathon demo for adults 18+. We never store your photo. "
    "When you run an analysis, your photo is held in memory only long enough to send it "
    "to the YouCam API (Perfect Corp) for skin analysis, then discarded. We keep your "
    "display name, consent, the 15 skin scores plus skin type and the analysis masks, "
    "linked to a cookie in your browser; only you and the person running this demo can "
    "see them, except the public sample profile. YouCam may keep the "
    "uploaded photo for up to 30 days under its own terms. Your photo is never sent to "
    "any other AI or service and is never used for training. Only analyze your own face. "
    "Delete your profile at any time from the People page; that removes everything "
    "SkinLedger stores about you."
)
