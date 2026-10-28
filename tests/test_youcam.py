"""P03 client tests: mocked 4-step flow, retries, parsing and mock mode (no network)."""

import copy
import io
import json
from pathlib import Path

import httpx
import pytest
import respx
from PIL import Image

from skinledger import mock_masks
from skinledger.aspects import SD_ACTIONS
from skinledger.imaging import PreparedImage
from skinledger.youcam import (
    AUTH_UNAVAILABLE_MESSAGE,
    DEFAULT_SKIN_TYPE_KEY,
    FRIENDLY_ERRORS,
    YouCamAPIError,
    YouCamAuthError,
    YouCamClient,
    YouCamConfigError,
    YouCamInvalidActionError,
    YouCamTaskError,
)

pytestmark = pytest.mark.asyncio

BASE = "https://yce.unit.test"
FILE_URL = f"{BASE}/s2s/v2.0/file"
TASK_URL = f"{BASE}/s2s/v2.0/task/skin-analysis"
SIGNED_PUT = "https://upload.unit.test/put/abc"

FIXTURE = json.loads(
    (Path(__file__).resolve().parent / "fixtures" / "sd_result_SAMPLE.json").read_text(
        encoding="utf-8"
    )
)
SAMPLE_SUCCESS = copy.deepcopy(FIXTURE)
RUNNING = {"data": {"task_status": "running"}}


def sample_image() -> PreparedImage:
    return PreparedImage(
        data=b"prepared-jpeg-bytes", content_type="image/jpeg", width=900, height=1200
    )


async def no_sleep(_seconds: float) -> None:
    return None


def make_client(**overrides) -> YouCamClient:
    params = {
        "api_key": "unit-test-key",
        "base_url": BASE,
        "version": "v2.0",
        "mock": False,
        "poll_interval": 0,
        "poll_timeout": 1,
        "sleep": no_sleep,
    }
    params.update(overrides)
    return YouCamClient(**params)


def file_response() -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "data": {
                "files": [
                    {
                        "file_id": "file-abc",
                        "requests": [
                            {
                                "method": "PUT",
                                "url": SIGNED_PUT,
                                "headers": {
                                    "Content-Type": "image/jpeg",
                                    "Content-Length": str(len(sample_image().data)),
                                },
                            }
                        ],
                    }
                ]
            }
        },
    )


@respx.mock
async def test_happy_four_step_flow():
    file_route = respx.post(FILE_URL).mock(return_value=file_response())
    respx.put(SIGNED_PUT).mock(return_value=httpx.Response(200))
    task_route = respx.post(TASK_URL).mock(
        return_value=httpx.Response(200, json={"data": {"task_id": "task-abc"}})
    )
    respx.get(f"{TASK_URL}/task-abc").mock(
        return_value=httpx.Response(200, json=SAMPLE_SUCCESS)
    )

    client = make_client()
    image = sample_image()
    file_id = await client.upload_file(image)
    task_id = await client.create_task(file_id)
    result = await client.get_task(task_id)

    assert file_id == "file-abc"
    assert task_id == "task-abc"
    assert result.status == "success"
    assert len(result.scores) == 15
    assert result.scores["moisture"] == 52.0
    assert result.categorical["skin_type_whole"] == "Combination"
    assert result.mask_urls["acne"][0].startswith("https://results.example.invalid/mask/acne")
    assert result.error_code is None

    assert json.loads(file_route.calls[0].request.content) == {
        "files": [
            {
                "content_type": "image/jpeg",
                "file_name": "capture.jpg",
                "file_size": len(image.data),
            }
        ]
    }
    assert task_route.calls[0].request.headers["content-type"] == "application/json"


@respx.mock
async def test_put_uses_returned_headers_without_authorization():
    put_route = respx.put(SIGNED_PUT).mock(return_value=httpx.Response(200))
    respx.post(FILE_URL).mock(return_value=file_response())

    await make_client().upload_file(sample_image())

    request = put_route.calls[0].request
    assert request.content == sample_image().data
    assert request.headers["content-type"] == "image/jpeg"
    assert request.headers["content-length"] == str(len(sample_image().data))
    assert "authorization" not in request.headers


@respx.mock
async def test_create_task_sends_sixteen_sd_actions_as_json():
    task_route = respx.post(TASK_URL).mock(
        return_value=httpx.Response(200, json={"data": {"task_id": "task-abc"}})
    )

    await make_client().create_task("file-abc")

    payload = json.loads(task_route.calls[0].request.content)
    assert payload["src_file_id"] == "file-abc"
    assert payload["dst_actions"] == list(SD_ACTIONS)
    assert payload["format"] == "json"
    assert "miniserver_args" not in payload


@respx.mock
async def test_create_task_can_request_mask_overlay():
    task_route = respx.post(TASK_URL).mock(
        return_value=httpx.Response(200, json={"data": {"task_id": "task-abc"}})
    )

    await make_client().create_task("file-abc", mask_overlay=True)

    payload = json.loads(task_route.calls[0].request.content)
    assert payload["miniserver_args"] == {"enable_mask_overlay": True}


@respx.mock
async def test_poll_running_running_success():
    route = respx.get(f"{TASK_URL}/task-abc").mock(
        side_effect=[
            httpx.Response(200, json=RUNNING),
            httpx.Response(200, json=RUNNING),
            httpx.Response(200, json=SAMPLE_SUCCESS),
        ]
    )

    result = await make_client().poll("task-abc", interval=0, timeout=5)

    assert result.status == "success"
    assert route.call_count == 3


@respx.mock
async def test_task_error_raises_typed_exception_with_friendly_message():
    body = {
        "data": {
            "task_status": "error",
            "error": {"code": "error_src_face_too_small"},
        }
    }
    respx.get(f"{TASK_URL}/task-abc").mock(return_value=httpx.Response(200, json=body))

    with pytest.raises(YouCamTaskError) as excinfo:
        await make_client().poll("task-abc", interval=0, timeout=5)

    assert excinfo.value.error_code == "error_src_face_too_small"
    assert str(excinfo.value) == FRIENDLY_ERRORS["error_src_face_too_small"]


@respx.mock
async def test_task_error_code_can_live_in_results():
    body = {
        "data": {
            "task_status": "error",
            "results": {"error": "error_multiple_people"},
        }
    }
    route = respx.get(f"{TASK_URL}/task-abc").mock(return_value=httpx.Response(200, json=body))

    result = await make_client().get_task("task-abc")

    assert result.status == "error"
    assert result.error_code == "error_multiple_people"
    assert route.call_count == 1


@respx.mock
async def test_rate_limit_honours_retry_after():
    delays: list[float] = []

    async def record_sleep(seconds: float) -> None:
        delays.append(seconds)

    route = respx.get(f"{TASK_URL}/task-abc").mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "1"}),
            httpx.Response(200, json=SAMPLE_SUCCESS),
        ]
    )

    result = await make_client(sleep=record_sleep).get_task("task-abc")

    assert result.status == "success"
    assert route.call_count == 2
    assert delays == [1.0]


@respx.mock
async def test_unauthorized_message_does_not_leak_the_key():
    respx.post(FILE_URL).mock(
        return_value=httpx.Response(401, json={"error": {"code": "InvalidAccessToken"}})
    )

    with pytest.raises(YouCamAuthError) as excinfo:
        await make_client().upload_file(sample_image())

    assert str(excinfo.value) == AUTH_UNAVAILABLE_MESSAGE
    assert "unit-test-key" not in str(excinfo.value)


@respx.mock
async def test_hd_action_is_rejected_locally_without_request():
    with respx.mock as router:
        with pytest.raises(YouCamInvalidActionError):
            await make_client().create_task("file-abc", actions=["hd_pore"])
        assert len(router.calls) == 0


async def test_unknown_action_is_rejected_locally():
    client = make_client()

    with pytest.raises(YouCamInvalidActionError):
        await client.create_task("file-abc", actions=["moisture", "not_an_aspect"])


@respx.mock
async def test_opaque_numeric_task_id_is_kept_exact():
    task_id = "123456789012345678901"
    route = respx.get(f"{TASK_URL}/{task_id}").mock(
        return_value=httpx.Response(200, json=RUNNING)
    )

    result = await make_client().get_task(task_id)

    assert result.status == "running"
    assert route.called
    assert task_id in str(route.calls[0].request.url)


@respx.mock
async def test_ui_score_is_dropped_from_result_and_raw():
    respx.get(f"{TASK_URL}/task-abc").mock(
        return_value=httpx.Response(200, json=SAMPLE_SUCCESS)
    )

    result = await make_client().get_task("task-abc")

    def keys(value):
        if isinstance(value, dict):
            for key, item in value.items():
                yield key
                yield from keys(item)
        elif isinstance(value, list):
            for item in value:
                yield from keys(item)

    assert not hasattr(result, "ui_score")
    assert "ui_score" not in set(keys(result.raw))


@respx.mock
async def test_signed_mask_urls_are_redacted_in_raw():
    respx.get(f"{TASK_URL}/task-abc").mock(
        return_value=httpx.Response(200, json=SAMPLE_SUCCESS)
    )

    result = await make_client().get_task("task-abc")
    stored = json.dumps(result.raw)

    assert "signature=" not in stored
    assert "?<signed>" in stored


@respx.mock
async def test_poll_timeout_returns_status_without_losing_task_id():
    route = respx.get(f"{TASK_URL}/task-abc").mock(
        return_value=httpx.Response(200, json=RUNNING)
    )

    result = await make_client().poll("task-abc", interval=0, timeout=0)

    assert result.status == "timeout"
    assert route.call_count == 1


@respx.mock
async def test_expired_mask_url_refreshes_task_once():
    old_url = "https://results.unit.test/mask/acne_0.png?signature=old"
    new_url = "https://results.unit.test/mask/acne_0.png?signature=new"
    old_body = copy.deepcopy(SAMPLE_SUCCESS)
    new_body = copy.deepcopy(SAMPLE_SUCCESS)
    for body, url in ((old_body, old_url), (new_body, new_url)):
        acne = next(
            item
            for item in body["data"]["results"]["output"]
            if item.get("type") == "acne"
        )
        acne["mask_urls"] = [url]

    task_route = respx.get(f"{TASK_URL}/task-exp").mock(
        side_effect=[
            httpx.Response(200, json=old_body),
            httpx.Response(200, json=new_body),
        ]
    )
    respx.get(old_url).mock(return_value=httpx.Response(403))
    new_route = respx.get(new_url).mock(
        return_value=httpx.Response(200, content=b"fresh-mask")
    )

    client = make_client()
    result = await client.get_task("task-exp")
    data = await client.download(result.mask_urls["acne"][0], task_id="task-exp")

    assert data == b"fresh-mask"
    assert task_route.call_count == 2
    assert new_route.called


@respx.mock
async def test_resize_image_entry_is_never_exposed_or_stored():
    route = respx.get(f"{TASK_URL}/task-abc").mock(
        return_value=httpx.Response(200, json=SAMPLE_SUCCESS)
    )

    result = await make_client().get_task("task-abc")
    stored = json.dumps(result.raw)

    assert "resize_image" not in result.scores
    assert "resize_image" not in result.mask_urls
    assert all(
        item.get("type") != "resize_image"
        for item in result.raw["data"]["results"]["output"]
    )
    assert "resized/photo_0" not in stored
    assert route.call_count == 1


@respx.mock
async def test_skin_type_regions_are_keyed_and_whole_is_the_default():
    respx.get(f"{TASK_URL}/task-abc").mock(
        return_value=httpx.Response(200, json=SAMPLE_SUCCESS)
    )

    result = await make_client().get_task("task-abc")

    assert result.categorical == {
        "skin_type_whole": "Combination",
        "skin_type_t_zone": "Oily",
        "skin_type_u_zone": "Dry",
    }
    assert set(result.mask_urls) >= {
        "skin_type_whole",
        "skin_type_t_zone",
        "skin_type_u_zone",
    }
    assert DEFAULT_SKIN_TYPE_KEY == "skin_type_whole"


@respx.mock
async def test_all_and_skin_age_scores_stay_only_in_raw():
    respx.get(f"{TASK_URL}/task-abc").mock(
        return_value=httpx.Response(200, json=SAMPLE_SUCCESS)
    )

    result = await make_client().get_task("task-abc")
    entries = {
        item["type"]: item for item in result.raw["data"]["results"]["output"]
    }

    for raw_only in ("all", "skin_age"):
        assert raw_only not in result.scores
        assert raw_only not in result.mask_urls
    assert entries["all"]["score"] == 64.0
    assert entries["skin_age"]["score"] == 32.0
    assert "ui_score" not in entries["all"]


@respx.mock
async def test_missing_optional_blocks_do_not_crash():
    body = {
        "data": {
            "task_status": "success",
            "results": {
                "output": [
                    {
                        "type": "skin_type",
                        "region": "whole",
                        "skin_type": "Oily",
                        "mask_urls": [],
                    },
                    {"type": "moisture", "raw_score": 55, "mask_urls": []},
                ]
            },
        }
    }
    respx.get(f"{TASK_URL}/task-cat").mock(return_value=httpx.Response(200, json=body))

    result = await make_client().get_task("task-cat")

    assert result.status == "success"
    assert result.scores == {"moisture": 55.0}
    assert result.categorical == {"skin_type_whole": "Oily"}
    assert "skin_age" not in result.raw["data"]["results"]


@respx.mock
async def test_unknown_aspect_is_kept_in_raw_and_does_not_crash():
    body = {
        "data": {
            "task_status": "success",
            "results": {"output": [{"type": "future_metric", "raw_score": 42}]},
        }
    }
    respx.get(f"{TASK_URL}/task-new").mock(return_value=httpx.Response(200, json=body))

    result = await make_client().get_task("task-new")

    assert result.scores == {"future_metric": 42.0}
    assert result.raw["data"]["results"]["output"][0]["type"] == "future_metric"


@respx.mock
async def test_server_errors_retried_for_get_but_not_for_create_task():
    get_route = respx.get(f"{TASK_URL}/task-abc").mock(
        side_effect=[
            httpx.Response(500),
            httpx.Response(502),
            httpx.Response(200, json=SAMPLE_SUCCESS),
        ]
    )
    result = await make_client().get_task("task-abc")
    assert result.status == "success"
    assert get_route.call_count == 3

    post_route = respx.post(TASK_URL).mock(return_value=httpx.Response(500))
    with pytest.raises(YouCamAPIError):
        await make_client().create_task("file-abc")
    assert post_route.call_count == 1


@respx.mock
async def test_mock_mode_runs_the_whole_flow_without_network():
    client = YouCamClient(mock=True, sleep=no_sleep, poll_interval=0)
    with respx.mock as router:
        file_id = await client.upload_file(sample_image())
        task_id = await client.create_task(file_id)
        assert (await client.get_task(task_id)).status == "running"
        assert (await client.get_task(task_id)).status == "running"
        result = await client.poll(task_id)
        mask = await client.download(result.mask_urls["acne"][0])

        assert len(router.calls) == 0

    assert result.status == "success"
    assert len(result.scores) == 15
    assert result.categorical["skin_type_whole"] == "Combination"
    assert result.raw["_label"] == "SAMPLE"
    with Image.open(io.BytesIO(mask)) as mask_image:
        assert mask_image.format == "PNG"
        assert mask_image.mode == "RGBA"
        assert mask_image.size == (mock_masks.MASK_WIDTH, mock_masks.MASK_HEIGHT)


@respx.mock
async def test_missing_key_in_real_mode_raises_config_error():
    with respx.mock as router:
        client = YouCamClient(api_key="", mock=False, sleep=no_sleep)
        with pytest.raises(YouCamConfigError) as excinfo:
            await client.upload_file(sample_image())

        assert str(excinfo.value) == "YOUCAM_API_KEY is not set"
        assert len(router.calls) == 0


@respx.mock
async def test_credit_balance_sums_api_types():
    respx.get(f"{BASE}/s2s/v1.0/client/credit").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {"type": "Api", "amount": "100"},
                    {"type": "ApiExtra", "amount": 50},
                    {"type": "Other", "amount": 999},
                ]
            },
        )
    )

    assert await make_client().get_credit_balance() == 150.0


@respx.mock
async def test_credit_balance_returns_none_when_unavailable():
    route = respx.get(f"{BASE}/s2s/v1.0/client/credit").mock(
        return_value=httpx.Response(500)
    )

    assert await make_client().get_credit_balance() is None
    assert route.call_count == 3
