"""YouCam Skin Analysis client: the only module that reads YOUCAM_API_KEY."""

from __future__ import annotations

import asyncio
import copy
import io
import json
import logging
import random
from collections.abc import Awaitable, Callable, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx
from PIL import Image
from pydantic import SecretStr

from skinledger.aspects import SD_ACTIONS
from skinledger.config import get_settings
from skinledger.imaging import PreparedImage

logger = logging.getLogger(__name__)

JSON_TIMEOUT = httpx.Timeout(30.0)
UPLOAD_TIMEOUT = httpx.Timeout(120.0)
MAX_ATTEMPTS = 4
MAX_SERVER_RETRIES = 2
MAX_BACKOFF_S = 8.0

# The file endpoint is documented as v2.0; only the task endpoint follows YOUCAM_SKIN_VERSION.
FILE_API_VERSION = "v2.0"

MOCK_RUNNING_POLLS = 2
MOCK_POLL_INTERVAL_S = 0.5
MOCK_MASK_SIZE = (64, 48)

SAMPLE_FIXTURE_PATH = (
    Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "sd_result_SAMPLE.json"
)

AUTH_UNAVAILABLE_MESSAGE = "Analysis is temporarily unavailable."

FRIENDLY_ERRORS: dict[str, str] = {
    "error_src_face_too_small": "Move closer: your face should fill most of the frame.",
    "error_src_face_out_of_bound": "Center your whole face inside the frame.",
    "error_lighting_dark": "Too dark. Face a window or a soft light and try again.",
    "error_below_min_image_size": (
        "This photo can't be used. Please upload a JPG or PNG under 10 MB, at least 480 px "
        "on the short side — or use the guided camera."
    ),
    "error_exceed_max_image_size": (
        "This photo can't be used. Please upload a JPG or PNG under 10 MB, at least 480 px "
        "on the short side — or use the guided camera."
    ),
    "exceed_max_filesize": (
        "This photo can't be used. Please upload a JPG or PNG under 10 MB, at least 480 px "
        "on the short side — or use the guided camera."
    ),
    "unsupported_format": (
        "This photo can't be used. Please upload a JPG or PNG under 10 MB, at least 480 px "
        "on the short side — or use the guided camera."
    ),
    "error_no_face": "We couldn't find a face. Use a front-facing photo of your own face.",
    "error_large_face_angle": "Keep your head straight and look at the camera.",
    "error_multiple_people": "Only one person should be in the photo.",
    "error_decode_image": "The photo couldn't be read. Please try another one.",
    "error_download_image": "The photo couldn't be read. Please try another one.",
    "error_face_parsing": (
        "The analysis service had a problem. No units were charged. Try again in a minute."
    ),
    "error_inference": (
        "The analysis service had a problem. No units were charged. Try again in a minute."
    ),
    "unknown_internal_error": (
        "The analysis service had a problem. No units were charged. Try again in a minute."
    ),
    "unknown_task_error": (
        "The analysis service had a problem. No units were charged. Try again in a minute."
    ),
}

GENERIC_ERROR_MESSAGE = FRIENDLY_ERRORS["unknown_internal_error"]

# Image problems detected locally or by YouCam. The UI appends
# "This attempt didn't count toward your limit." when it shows one of these.
IMAGE_ERROR_CODES = frozenset(
    {
        "error_below_min_image_size",
        "error_exceed_max_image_size",
        "exceed_max_filesize",
        "unsupported_format",
    }
)


class YouCamError(Exception):
    """Base class for every error raised by this module."""

    user_message = GENERIC_ERROR_MESSAGE


class YouCamConfigError(YouCamError):
    """Configuration problem, e.g. a missing API key."""


class YouCamAuthError(YouCamError):
    """The API rejected the credentials."""

    user_message = AUTH_UNAVAILABLE_MESSAGE

    def __init__(self) -> None:
        super().__init__(AUTH_UNAVAILABLE_MESSAGE)


class YouCamAPIError(YouCamError):
    """A request failed (HTTP status, unreadable body or network problem)."""

    def __init__(self, message: str = GENERIC_ERROR_MESSAGE, *, code: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.user_message = message


class YouCamInvalidActionError(YouCamError, ValueError):
    """An action list contains HD or unknown aspects; rejected before any request."""


class YouCamTaskError(YouCamError):
    """The analysis task finished with an error status (no units were charged)."""

    def __init__(self, error_code: str) -> None:
        self.error_code = error_code
        self.user_message = FRIENDLY_ERRORS.get(error_code, GENERIC_ERROR_MESSAGE)
        super().__init__(self.user_message)


@dataclass(slots=True)
class TaskResult:
    """Parsed Skin Analysis task state, without ui_score and without signed URLs."""

    status: str
    scores: dict[str, float | None] = field(default_factory=dict)
    categorical: dict[str, str] = field(default_factory=dict)
    mask_urls: dict[str, list[str]] = field(default_factory=dict)
    error_code: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


def friendly_message(error_code: str | None) -> str:
    """Return the English user message for a YouCam error code."""
    if not error_code:
        return GENERIC_ERROR_MESSAGE
    return FRIENDLY_ERRORS.get(error_code, GENERIC_ERROR_MESSAGE)


def _as_code(value: Any) -> str | None:
    if isinstance(value, str) and value:
        return value
    if isinstance(value, dict):
        for key in ("code", "error_code", "error", "message"):
            inner = value.get(key)
            if isinstance(inner, str) and inner:
                return inner
    return None


def _sanitize_raw(value: Any) -> Any:
    """Drop ui_score everywhere and redact signed query strings from URLs."""
    if isinstance(value, dict):
        return {
            key: _sanitize_raw(item)
            for key, item in value.items()
            if key != "ui_score"
        }
    if isinstance(value, list):
        return [_sanitize_raw(item) for item in value]
    if isinstance(value, str) and value.startswith(("http://", "https://")) and "?" in value:
        return value.split("?", 1)[0] + "?<signed>"
    return value


def _url_list(value: Any) -> list[str]:
    if isinstance(value, str) and value:
        return [value]
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value if isinstance(item, str) and item]
    if isinstance(value, dict):
        urls: list[str] = []
        for item in value.values():
            urls.extend(_url_list(item))
        return urls
    return []


def load_sample_fixture() -> dict[str, Any]:
    """Load the SAMPLE result fixture used by mock mode (never a real capture)."""
    return json.loads(SAMPLE_FIXTURE_PATH.read_text(encoding="utf-8"))


_ANALYSIS_SEMAPHORE = asyncio.Semaphore(1)


@asynccontextmanager
async def analysis_slot():
    """Allow one analysis at a time per process (the pipeline wraps a whole run)."""
    async with _ANALYSIS_SEMAPHORE:
        yield


class YouCamClient:
    """Async client for the 4-step YouCam Skin Analysis SD flow."""

    def __init__(
        self,
        *,
        api_key: str | SecretStr | None = None,
        base_url: str | None = None,
        version: str | None = None,
        mock: bool | None = None,
        poll_interval: float | None = None,
        poll_timeout: float | None = None,
        sleep: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        settings = get_settings()
        if api_key is None:
            api_key = settings.youcam_api_key
        self._api_key = api_key.get_secret_value() if isinstance(api_key, SecretStr) else api_key
        self._base_url = (base_url or settings.youcam_base_url).rstrip("/")
        self._version = version or settings.youcam_skin_version
        self.mock = settings.youcam_mock if mock is None else mock
        if poll_interval is not None:
            self.poll_interval = poll_interval
        elif self.mock:
            self.poll_interval = MOCK_POLL_INTERVAL_S
        else:
            self.poll_interval = float(settings.youcam_poll_interval_s)
        self.poll_timeout = (
            float(poll_timeout)
            if poll_timeout is not None
            else float(settings.youcam_poll_timeout_s)
        )
        self._sleep = sleep or asyncio.sleep

        self._mock_file_counter = 0
        self._mock_task_counter = 0
        self._mock_task_polls: dict[str, int] = {}
        self._mock_masks: dict[str, bytes] = {}

    # -- auth and low-level HTTP ------------------------------------------------

    def _auth_headers(self) -> dict[str, str]:
        if not self._api_key:
            raise YouCamConfigError("YOUCAM_API_KEY is not set")
        return {"Authorization": f"Bearer {self._api_key}"}

    async def _request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        json_body: dict[str, Any] | None = None,
        content: bytes | None = None,
        timeout: httpx.Timeout = JSON_TIMEOUT,
        retry_server_errors: bool = True,
    ) -> httpx.Response:
        attempt = 0
        while True:
            attempt += 1
            try:
                async with httpx.AsyncClient(timeout=timeout) as http:
                    response = await http.request(
                        method, url, headers=headers, json=json_body, content=content
                    )
            except httpx.HTTPError as exc:
                if retry_server_errors and attempt <= MAX_SERVER_RETRIES:
                    await self._sleep(self._backoff(attempt))
                    continue
                logger.warning("YouCam request failed: %s", type(exc).__name__)
                raise YouCamAPIError() from exc

            if response.status_code == 429:
                if attempt >= MAX_ATTEMPTS:
                    raise YouCamAPIError(
                        "The analysis service is busy. No units were charged. "
                        "Try again in a minute."
                    )
                await self._sleep(self._throttle_delay(response, attempt))
                continue

            if (
                response.status_code >= 500
                and retry_server_errors
                and attempt <= MAX_SERVER_RETRIES
            ):
                await self._sleep(self._backoff(attempt))
                continue

            return response

    def _backoff(self, attempt: int) -> float:
        return min(2.0 ** (attempt - 1), MAX_BACKOFF_S) + random.uniform(0.0, 0.25)

    def _throttle_delay(self, response: httpx.Response, attempt: int) -> float:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return max(0.0, min(float(retry_after), 60.0))
            except ValueError:
                pass
        return self._backoff(attempt)

    def _raise_for_http_error(self, response: httpx.Response) -> None:
        if response.status_code < 400:
            return
        try:
            body = response.json()
        except ValueError:
            body = None
        code = None
        if isinstance(body, dict):
            for candidate in (
                body.get("error"),
                body.get("code"),
                _dig(body, "data", "error"),
                _dig(body, "data", "error_code"),
            ):
                code = _as_code(candidate)
                if code:
                    break

        if response.status_code == 401 or code == "InvalidAccessToken":
            logger.warning(
                "YouCam returned 401 InvalidAccessToken; check YOUCAM_API_KEY (value not logged)"
            )
            raise YouCamAuthError()
        if code and "InvalidTaskId" in code:
            raise YouCamTaskError("InvalidTaskId")
        if response.status_code == 400 and code == "InvalidParameters":
            logger.error("YouCam rejected the request as invalid parameters (programming error)")
            raise YouCamAPIError(code=code)
        raise YouCamAPIError(code=code)

    async def _request_json(
        self,
        method: str,
        url: str,
        *,
        json_body: dict[str, Any] | None = None,
        retry_server_errors: bool = True,
    ) -> dict[str, Any]:
        response = await self._request(
            method,
            url,
            headers={**self._auth_headers(), "Content-Type": "application/json"},
            json_body=json_body,
            retry_server_errors=retry_server_errors,
        )
        self._raise_for_http_error(response)
        try:
            body = response.json()
        except ValueError:
            raise YouCamAPIError() from None
        if not isinstance(body, dict):
            raise YouCamAPIError()
        return body

    # -- step 1: file upload ----------------------------------------------------

    async def upload_file(self, img: PreparedImage, file_name: str = "capture.jpg") -> str:
        """POST the file metadata, then PUT the bytes to the signed URL (no auth header)."""
        if self.mock:
            self._mock_file_counter += 1
            return f"mock-file-{self._mock_file_counter}"

        payload = {
            "files": [
                {
                    "content_type": img.content_type,
                    "file_name": file_name,
                    "file_size": len(img.data),
                }
            ]
        }
        body = await self._request_json(
            "POST",
            f"{self._base_url}/s2s/{FILE_API_VERSION}/file",
            json_body=payload,
            retry_server_errors=False,
        )
        files = _dig(body, "data", "files")
        try:
            entry = files[0]
            file_id = str(entry["file_id"])
            request = entry["requests"][0]
        except (KeyError, IndexError, TypeError):
            raise YouCamAPIError() from None

        method = str(request.get("method") or "PUT").upper()
        url = request.get("url")
        returned_headers = request.get("headers") or {}
        if not isinstance(url, str) or not url or not isinstance(returned_headers, dict):
            raise YouCamAPIError()

        response = await self._request(
            method,
            url,
            headers={str(key): str(value) for key, value in returned_headers.items()},
            content=img.data,
            timeout=UPLOAD_TIMEOUT,
            retry_server_errors=True,
        )
        self._raise_for_http_error(response)
        return file_id

    # -- step 2: create the analysis task ---------------------------------------

    async def create_task(
        self,
        file_id: str,
        actions: Sequence[str] = SD_ACTIONS,
        mask_overlay: bool = False,
    ) -> str:
        """Create a Skin Analysis task. Never retried automatically (it charges units)."""
        actions = list(actions)
        invalid = [
            str(action)
            for action in actions
            if not isinstance(action, str)
            or action.startswith("hd_")
            or action not in SD_ACTIONS
        ]
        if invalid or not actions:
            raise YouCamInvalidActionError(
                f"Unsupported Skin Analysis actions: {', '.join(invalid) or '(none)'}"
            )

        if self.mock:
            self._mock_task_counter += 1
            return f"mock-task-{self._mock_task_counter}"

        payload: dict[str, Any] = {
            "src_file_id": str(file_id),
            "dst_actions": actions,
            "format": "json",
        }
        if mask_overlay:
            payload["miniserver_args"] = {"enable_mask_overlay": True}

        body = await self._request_json(
            "POST",
            f"{self._base_url}/s2s/{self._version}/task/skin-analysis",
            json_body=payload,
            retry_server_errors=False,
        )
        task_id = _dig(body, "data", "task_id")
        if not isinstance(task_id, str) or not task_id:
            raise YouCamAPIError()
        return task_id

    # -- step 3: read the task --------------------------------------------------

    async def get_task(self, task_id: str) -> TaskResult:
        """GET the task state and parse it tolerantly. Never casts IDs to int."""
        task_id = str(task_id)
        if self.mock:
            seen = self._mock_task_polls.get(task_id, 0) + 1
            self._mock_task_polls[task_id] = seen
            if seen <= MOCK_RUNNING_POLLS:
                return TaskResult(status="running")
            return self._parse_task_body(self._mock_success_body(task_id))

        body = await self._request_json(
            "GET",
            f"{self._base_url}/s2s/{self._version}/task/skin-analysis/{task_id}",
            retry_server_errors=True,
        )
        return self._parse_task_body(body)

    def _parse_task_body(self, body: dict[str, Any]) -> TaskResult:
        data = body.get("data")
        if not isinstance(data, dict):
            data = {}
        status = str(data.get("task_status") or body.get("task_status") or "unknown")
        raw = _sanitize_raw(body)

        scores: dict[str, float | None] = {}
        categorical: dict[str, str] = {}
        mask_urls: dict[str, list[str]] = {}

        results = data.get("results")
        output = results.get("output") if isinstance(results, dict) else None
        if not isinstance(output, list):
            output = []

        for item in output:
            if not isinstance(item, dict):
                continue
            aspect = item.get("type") or item.get("aspect")
            if not isinstance(aspect, str) or not aspect:
                continue

            urls = _url_list(item.get("mask_urls"))
            if urls:
                mask_urls[aspect] = urls

            if aspect == "skin_type":
                # UNVERIFIED: skin_type may be categorical or carry whole/t_zone/u_zone.
                value = item.get("skin_type", item.get("value", item.get("raw_score")))
                if isinstance(value, dict):
                    categorical[aspect] = json.dumps(value, sort_keys=True)
                elif value is not None:
                    categorical[aspect] = str(value)
                continue

            raw_score = item.get("raw_score")
            if isinstance(raw_score, bool) or not isinstance(raw_score, (int, float)):
                scores[aspect] = None
            else:
                scores[aspect] = float(raw_score)

            if aspect not in SD_ACTIONS:
                # UNVERIFIED: an unknown aspect must stay in the raw JSON and never crash.
                logger.debug("Unknown aspect %r kept only in the raw JSON", aspect)

        error_code = None
        if status == "error":
            error_code = self._extract_task_error_code(data)

        return TaskResult(
            status=status,
            scores=scores,
            categorical=categorical,
            mask_urls=mask_urls,
            error_code=error_code,
            raw=raw,
        )

    def _extract_task_error_code(self, data: dict[str, Any]) -> str:
        # UNVERIFIED: the docs do not say which field carries the error code.
        results = data.get("results")
        if not isinstance(results, dict):
            results = {}
        for candidate in (
            data.get("error"),
            data.get("error_code"),
            results.get("error"),
        ):
            code = _as_code(candidate)
            if code:
                return code
        return "unknown_task_error"

    # -- step 4: poll -----------------------------------------------------------

    async def poll(
        self,
        task_id: str,
        interval: float | None = None,
        timeout: float | None = None,
    ) -> TaskResult:
        """Poll until success or error; on timeout return status='timeout'.

        The caller keeps the task_id (valid 30 days) and can resume later.
        """
        task_id = str(task_id)
        interval = self.poll_interval if interval is None else float(interval)
        timeout = self.poll_timeout if timeout is None else float(timeout)
        loop = asyncio.get_running_loop()
        started = loop.time()

        while True:
            result = await self.get_task(task_id)
            if result.status == "success":
                return result
            if result.status == "error":
                raise YouCamTaskError(result.error_code or "unknown_task_error")
            remaining = timeout - (loop.time() - started)
            if remaining <= 0:
                return TaskResult(status="timeout")
            await self._sleep(min(interval, remaining))

    # -- masks and balance ------------------------------------------------------

    async def download(self, url: str, task_id: str | None = None) -> bytes:
        """Download a mask without the Authorization header; refresh once if expired."""
        if self.mock:
            return self._mock_mask_png(url)

        response = await self._request("GET", url, retry_server_errors=True)
        if response.status_code in (403, 404) and task_id:
            logger.info(
                "Mask URL expired (HTTP %s); refreshing it via the task",
                response.status_code,
            )
            refreshed = await self.get_task(task_id)
            fresh_url = _fresh_mask_url(refreshed, url)
            if fresh_url:
                response = await self._request("GET", fresh_url, retry_server_errors=True)
        self._raise_for_http_error(response)
        return response.content

    async def get_credit_balance(self) -> float | None:
        """Return spendable units or None. UNVERIFIED: endpoint from the official skills repo."""
        # UNVERIFIED: GET /s2s/v1.0/client/credit is not in the docs we read.
        if self.mock:
            return None
        try:
            body = await self._request_json(
                "GET", f"{self._base_url}/s2s/v1.0/client/credit", retry_server_errors=True
            )
            results = body.get("results")
            if not isinstance(results, list):
                return None
            total = 0.0
            for item in results:
                if isinstance(item, dict) and str(item.get("type", "")).startswith("Api"):
                    total += float(item.get("amount") or 0)
            return total
        except (YouCamError, TypeError, ValueError):
            return None

    # -- mock mode --------------------------------------------------------------

    def _mock_success_body(self, task_id: str) -> dict[str, Any]:
        body = copy.deepcopy(load_sample_fixture())
        data = body.setdefault("data", {})
        data["task_id"] = task_id
        results = data.get("results")
        output = results.get("output") if isinstance(results, dict) else None
        for item in output or []:
            if not isinstance(item, dict):
                continue
            aspect = item.get("type") or "aspect"
            count = len(_url_list(item.get("mask_urls"))) or 1
            item["mask_urls"] = [f"mock://mask/{aspect}/{index}.png" for index in range(count)]
        return body

    def _mock_mask_png(self, url: str) -> bytes:
        cached = self._mock_masks.get(url)
        if cached is None:
            buffer = io.BytesIO()
            # A flat grey PNG made in memory; never a face and never a real mask.
            Image.new("L", MOCK_MASK_SIZE, color=200).save(buffer, format="PNG")
            cached = buffer.getvalue()
            self._mock_masks[url] = cached
        return cached


def _dig(body: Any, *keys: str) -> Any:
    value = body
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _fresh_mask_url(result: TaskResult, old_url: str) -> str | None:
    old_path = old_url.split("?", 1)[0]
    for urls in result.mask_urls.values():
        for url in urls:
            if url == old_url or url.split("?", 1)[0] == old_path:
                return url
    for urls in result.mask_urls.values():
        if urls:
            return urls[0]
    return None


@lru_cache
def get_client() -> YouCamClient:
    """Process-wide client built from settings."""
    return YouCamClient()
