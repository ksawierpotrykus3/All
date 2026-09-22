"""Unit tests for DeepSeekClient.upload_file and multi-path PoW."""

from unittest.mock import MagicMock, patch
import pytest

from server.core.deepseek_client import DeepSeek, Session


@pytest.fixture
def mock_client():
    pool = MagicMock()
    pool.slots = [Session(auth_token="test_token", cookies={"token": "abc"}, user_agent="Chrome/120")]
    client = DeepSeek(pool)
    client.pow = MagicMock()
    client.pow.solve_challenge.return_value = "solved_pow_string"
    client._throttle = MagicMock()
    client.wait_for_file_ready = MagicMock(return_value=True)
    return client


def test_get_pow_with_target_path(mock_client):
    with patch.object(mock_client, "_prefetch_pow"), \
         patch.object(mock_client, "_get_challenge", return_value={"algorithm": "DeepSeekHashV1", "expire_at": 9999999999000}) as mock_challenge:
        pow1 = mock_client._get_pow(0, target_path="/api/v0/chat/completion")
        assert pow1 == "solved_pow_string"
        mock_challenge.assert_called_with(0, target_path="/api/v0/chat/completion")

        # Second call without prefetch must solve a fresh challenge (PoW tokens are single-use nonces)
        pow1_fresh = mock_client._get_pow(0, target_path="/api/v0/chat/completion")
        assert pow1_fresh == "solved_pow_string"
        assert mock_challenge.call_count == 2

        # Call with upload_file target_path should fetch separate challenge and NOT cache it
        pow2 = mock_client._get_pow(0, target_path="/api/v0/file/upload_file")
        assert pow2 == "solved_pow_string"
        assert mock_challenge.call_count == 3
        mock_challenge.assert_called_with(0, target_path="/api/v0/file/upload_file")

        # Second call with upload_file target_path must NOT hit cache (single-use token)
        pow2_fresh = mock_client._get_pow(0, target_path="/api/v0/file/upload_file")
        assert pow2_fresh == "solved_pow_string"
        assert mock_challenge.call_count == 4


def test_upload_file_retry_on_invalid_pow(mock_client):
    resp_fail = MagicMock()
    resp_fail.status_code = 200
    resp_fail.text = '{"code":40301,"msg":"INVALID_POW_RESPONSE","data":null}'
    resp_fail.json.return_value = {"code": 40301, "msg": "INVALID_POW_RESPONSE", "data": None}

    resp_ok = MagicMock()
    resp_ok.status_code = 200
    resp_ok.text = '{"code":0,"msg":"","data":{"biz_code":0,"biz_msg":"","biz_data":{"id":"file-retry-success"}}}'
    resp_ok.json.return_value = {
        "code": 0,
        "msg": "",
        "data": {"biz_code": 0, "biz_msg": "", "biz_data": {"id": "file-retry-success"}},
    }

    with patch("server.core.deepseek_client.requests.post", side_effect=[resp_fail, resp_ok]) as mock_post, \
         patch.object(mock_client, "_get_pow", return_value="pow_val") as mock_pow:
        fid = mock_client.upload_file(
            slot=0,
            file_data=b"test_image_bytes",
            filename="retry_test.png",
            mime_type="image/png",
            model_type="default",
        )
        assert fid == "file-retry-success"
        assert mock_post.call_count == 2
        assert mock_pow.call_count == 2


def test_upload_file_success(mock_client):
    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.text = '{"code":0,"msg":"","data":{"biz_code":0,"biz_msg":"","biz_data":{"id":"file-12345-abcde","status":"PENDING"}}}'
    fake_resp.json.return_value = {
        "code": 0,
        "msg": "",
        "data": {
            "biz_code": 0,
            "biz_msg": "",
            "biz_data": {
                "id": "file-12345-abcde",
                "status": "PENDING",
            },
        },
    }

    with patch("server.core.deepseek_client.requests.post", return_value=fake_resp) as mock_req_post, \
         patch.object(mock_client, "_get_pow", return_value="pow_val") as mock_pow:
        file_id = mock_client.upload_file(
            slot=0,
            file_data=b"test_image_bytes",
            filename="my_test.png",
            mime_type="image/png",
            model_type="default",
        )

        assert file_id == "file-12345-abcde"
        mock_pow.assert_called_with(
            0, target_path="/api/v0/file/upload_file", force_refresh=True
        )

        # Verify headers sent
        call_kwargs = mock_req_post.call_args[1]
        headers = call_kwargs["headers"]
        assert headers["x-ds-pow-response"] == "pow_val"
        assert headers["x-file-size"] == str(len(b"test_image_bytes"))
        assert headers["x-model-type"] == "default"
        assert headers["x-thinking-enabled"] == "1"
        assert "content-type" not in headers  # curl_cffi multipart sets its own


@pytest.mark.asyncio
async def test_proxy_service_image_injection_flow():
    import base64
    import json
    from server.services.proxy_service import ProxyService
    service = ProxyService()

    raw_bytes = b"sample_png_bytes"
    b64 = base64.b64encode(raw_bytes).decode("ascii")
    data_uri = f"data:image/png;base64,{b64}"

    req = {
        "model": "deepseek-v4-flash",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Analyze this image"},
                    {"type": "image_url", "image_url": {"url": data_uri}},
                ],
            }
        ],
        "stream": True,
    }

    from unittest.mock import AsyncMock
    mock_fastapi_req = MagicMock()
    mock_fastapi_req.headers = {}
    mock_fastapi_req.body = AsyncMock(return_value=json.dumps(req).encode("utf-8"))

    with patch("server.services.proxy_service.ds.upload_file", return_value="file-fake-img-id") as mock_upload, \
         patch("server.services.proxy_service.ds.create_session", return_value="sess_test"), \
         patch("server.services.proxy_service.ds.stream_completion") as mock_stream, \
         patch("server.services.proxy_service.ap.is_valid", return_value=True), \
         patch("server.services.proxy_service.session_manager.acquire_slot", return_value=True), \
         patch("server.services.proxy_service.session_manager.release_slot"), \
         patch("server.services.proxy_service.account_selector.select_account", return_value=0):

        mock_stream.return_value = (iter([]), {"resp_msg_id": "1", "chat_id": "sess_test"})

        response = await service.chat_completions(mock_fastapi_req)
        assert response is not None

        # Verify upload_file was called
        mock_upload.assert_called_once()
        upload_args = mock_upload.call_args
        assert upload_args.kwargs["file_data"] == raw_bytes
        assert upload_args.kwargs["mime_type"] == "image/png"

        # Verify stream_completion received ref_file_ids
        mock_stream.assert_called_once()
        stream_args = mock_stream.call_args
        assert stream_args.kwargs["ref_file_ids"] == ["file-fake-img-id"]
        # Positional arg 2 is prompt: ds.stream_completion(account_idx, chat_id, prompt, parent_id, ...)
        prompt_sent = stream_args[0][2]
        assert "[Image]" not in prompt_sent
        assert "Analyze this image" in prompt_sent


def test_upload_file_null_data_error(mock_client):
    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.text = '{"code":40001,"msg":"Invalid token or session expired","data":null}'
    fake_resp.json.return_value = {
        "code": 40001,
        "msg": "Invalid token or session expired",
        "data": None,
    }

    with patch("server.core.deepseek_client.requests.post", return_value=fake_resp), \
         patch.object(mock_client, "_get_pow", return_value="pow_val"):
        with pytest.raises(Exception) as exc_info:
            mock_client.upload_file(
                slot=0,
                file_data=b"test_image_bytes",
                filename="my_test.png",
                mime_type="image/png",
                model_type="default",
            )
        assert "DeepSeek file upload failed (code=40001): Invalid token or session expired" in str(exc_info.value)
        # Ensure 'NoneType' object has no attribute 'get' was NOT raised
        assert "NoneType" not in str(exc_info.value)


def test_get_challenge_null_data(mock_client):
    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.text = '{"code":500,"msg":"Internal cluster error","data":null}'
    fake_resp.json.return_value = {
        "code": 500,
        "msg": "Internal cluster error",
        "data": None,
    }

    mock_client._http[0] = MagicMock()
    mock_client._http[0].post.return_value = fake_resp

    with pytest.raises(RuntimeError) as exc_info:
        mock_client._get_challenge(0, target_path="/api/v0/file/upload_file")
    assert "DeepSeek PoW challenge failed" in str(exc_info.value)
    assert "NoneType" not in str(exc_info.value)


def test_build_stream_iterator_null_and_scalar_sse_lines(mock_client):
    pre_lines = [
        b'data: null\n',
        b'data: 12345\n',
        b'data: "string payload"\n',
        b'data: {"p": "response/fragments", "v": [{"type": "RESPONSE", "content": "Hello world!"}]}\n',
        b'data: {"p": "response/status", "o": "SET", "v": "FINISHED"}\n',
    ]
    it = iter([])
    stream_iter, meta = mock_client._build_stream_iterator(
        it=it,
        pre_lines=pre_lines,
        resp_msg_id=1,
        thinking_enabled=True,
        chat_session_id="test_sess",
        preamble_data_count=1,
    )

    chunks = list(stream_iter)
    assert "".join(chunks) == "Hello world!"


def test_wait_for_file_ready_polling(mock_client):
    # Restore unmocked wait_for_file_ready for this specific test
    mock_client.wait_for_file_ready = DeepSeek.wait_for_file_ready.__get__(mock_client, DeepSeek)
    
    resp_pending = MagicMock()
    resp_pending.status_code = 200
    resp_pending.json.return_value = {
        "data": {"biz_data": {"files": [{"status": "PARSING", "audit_result": "unknown"}]}}
    }

    resp_success = MagicMock()
    resp_success.status_code = 200
    resp_success.json.return_value = {
        "data": {"biz_data": {"files": [{"status": "SUCCESS", "audit_result": "pass"}]}}
    }

    mock_client._http[0] = MagicMock()
    mock_client._http[0].get.side_effect = [resp_pending, resp_success]

    ok = mock_client.wait_for_file_ready(0, "file-test-poll", timeout=5.0)
    assert ok is True
    assert mock_client._http[0].get.call_count == 2


