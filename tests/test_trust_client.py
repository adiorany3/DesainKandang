import base64
import io
import json

import pytest
import requests
from PIL import Image

from trust_client import (
    TrustAPIError, TrustServiceError, decode_image_response, generate_bynara_image,
    generate_image,
)


def png_bytes(size=(2, 3)):
    buffer = io.BytesIO()
    Image.new("RGB", size, "white").save(buffer, format="PNG")
    return buffer.getvalue()


class FakeResponse:
    def __init__(self, status_code=200, payload=None, content=b"", headers=None):
        self.status_code = status_code
        self._payload = payload
        if not content and payload is not None and not isinstance(payload, Exception):
            content = json.dumps(payload).encode()
        self.content = content
        self.headers = headers or {}

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload

    def iter_content(self, chunk_size):
        for start in range(0, len(self.content), chunk_size):
            yield self.content[start : start + chunk_size]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


@pytest.fixture(autouse=True)
def resolve_example_hosts_to_public_ip(monkeypatch):
    monkeypatch.setattr("trust_client.st.secrets", {
        "ENDPOINT": "https://api.trustisgold.web.id/v1/images/generations",
        "MODEL": "model-from-secrets",
        "NARA_MODEL": "gpt-image-2",
        "NARA_ENDPOINT": "https://api-images.bynara.id/v1/images/generations",
    })
    real_getaddrinfo = __import__("socket").getaddrinfo

    def fake_getaddrinfo(host, port, *args, **kwargs):
        if host in {"images.example", "example.test"}:
            return [(2, 1, 6, "", ("93.184.216.34", port))]
        return real_getaddrinfo(host, port, *args, **kwargs)

    monkeypatch.setattr("trust_client.socket.getaddrinfo", fake_getaddrinfo)


def test_decode_base64_png():
    expected = png_bytes()
    payload = {"data": [{"b64_json": base64.b64encode(expected).decode()}]}
    assert decode_image_response(payload) == expected

@pytest.mark.parametrize("format", ["JPEG", "WEBP"])
def test_decode_base64_other_image_formats_as_png(format):
    buffer = io.BytesIO()
    Image.new("RGB", (2, 3), "white").save(buffer, format=format)
    payload = {"data": [{"b64_json": base64.b64encode(buffer.getvalue()).decode()}]}
    result = decode_image_response(payload)
    with Image.open(io.BytesIO(result)) as image:
        assert image.format == "PNG"
        assert image.size == (2, 3)


def test_decode_url_jpeg_as_png():
    buffer = io.BytesIO()
    Image.new("RGB", (2, 3), "white").save(buffer, format="JPEG")

    def fake_get(*args, **kwargs):
        return FakeResponse(content=buffer.getvalue(), headers={"Content-Type": "image/jpeg"})

    result = decode_image_response(
        {"data": [{"url": "https://images.example/result.jpg"}]}, get_fn=fake_get
    )
    with Image.open(io.BytesIO(result)) as image:
        assert image.format == "PNG"
        assert image.size == (2, 3)

def test_decode_url_png_uses_bounded_download():
    expected = png_bytes()
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse(content=expected, headers={"Content-Type": "image/png"})

    payload = {"data": [{"url": "https://images.example/result.png"}]}
    assert decode_image_response(payload, get_fn=fake_get, timeout_s=7) == expected
    assert calls == [
        (
            "https://images.example/result.png",
            {"timeout": 7, "stream": True, "allow_redirects": False},
        )
    ]


@pytest.mark.parametrize(
    ("status", "text"), [(401, "API key"), (402, "kredit"), (429, "batas")]
)
def test_generate_image_translates_http_errors(status, text):
    def fake_post(*args, **kwargs):
        return FakeResponse(status_code=status, payload={"error": "sensitive"})

    with pytest.raises(TrustAPIError, match=f"(?i){text}"):
        generate_image("prompt", "TOP-SECRET", post_fn=fake_post)


def test_http_400_shows_safe_diagnostic_metadata_without_echoing_secrets():
    response = FakeResponse(status_code=400, payload={
        "error": {
            "type": "validation_error", "param": "model", "request_id": "req_abc123",
            "message": "Invalid TOP-SECRET and private prompt",
        }
    })
    with pytest.raises(TrustAPIError) as exc:
        generate_image("private prompt", "TOP-SECRET", post_fn=lambda *args, **kwargs: response)
    message = str(exc.value)
    assert "HTTP 400" in message
    assert "parameter: model" in message
    assert "req_abc123" in message
    assert "TOP-SECRET" not in message
    assert "private prompt" not in message


@pytest.mark.parametrize("payload", [
    {"error": {"type": "<script>", "param": "secret", "request_id": "req_<unsafe>"}},
    {"error": {"type": ["validation_error"], "param": {"model": "x"}}},
    {"error": "invalid"},
])
def test_http_400_ignores_untrusted_error_content(payload):
    response = FakeResponse(status_code=400, payload=payload)
    with pytest.raises(TrustAPIError) as exc:
        generate_image("prompt", "key", post_fn=lambda *args, **kwargs: response)
    assert "HTTP 400" in str(exc.value)
    assert "<" not in str(exc.value)
    assert "secret" not in str(exc.value)


def test_http_400_ignores_oversized_or_non_json_error_body():
    for body in (b"not json", b"x" * 9000):
        response = FakeResponse(status_code=400, content=body)
        with pytest.raises(TrustAPIError, match="HTTP 400"):
            generate_image("prompt", "key", post_fn=lambda *args, **kwargs: response)


def test_generate_image_sends_fixed_contract_without_leaking_key():
    expected = png_bytes()
    seen = {}

    def fake_post(url, *, headers, json, timeout, stream):
        seen.update(url=url, headers=headers, json=json, timeout=timeout, stream=stream)
        return FakeResponse(
            payload={"data": [{"b64_json": base64.b64encode(expected).decode()}]}
        )

    assert generate_image("kandang", "TOP-SECRET", post_fn=fake_post) == expected
    assert seen["url"] == "https://api.trustisgold.web.id/v1/images/generations"
    assert seen["json"] == {
        "model": "model-from-secrets",
        "prompt": "kandang",
        "size": "1024x1024",
        "quality": "medium",
        "n": 1,
    }
    assert seen["timeout"] == 180
    assert seen["headers"]["Authorization"] == "Bearer TOP-SECRET"


@pytest.mark.parametrize("endpoint", ["", "http://api.example/generate", "https://localhost:8443/generate", "https://user:pass@api.example/generate"])
def test_generate_image_rejects_missing_or_invalid_endpoint(monkeypatch, endpoint):
    monkeypatch.setattr("trust_client.st.secrets", {"ENDPOINT": endpoint})
    with pytest.raises(TrustAPIError, match="ENDPOINT"):
        generate_image("prompt", "key", post_fn=lambda *args, **kwargs: pytest.fail("Must not make request"))


@pytest.mark.parametrize("model", [None, "", "   ", 123])
def test_generate_image_rejects_missing_or_invalid_model(monkeypatch, model):
    monkeypatch.setattr("trust_client.st.secrets", {
        "ENDPOINT": "https://api.trustisgold.web.id/v1/images/generations",
        "MODEL": model,
    })
    with pytest.raises(TrustAPIError, match="MODEL"):
        generate_image("prompt", "key", post_fn=lambda *args, **kwargs: pytest.fail("Must not make request"))

def test_timeout_message_does_not_include_key():
    def fake_post(*args, **kwargs):
        raise requests.Timeout("TOP-SECRET")

    with pytest.raises(TrustAPIError) as error:
        generate_image("prompt", "TOP-SECRET", post_fn=fake_post)
    assert "TOP-SECRET" not in str(error.value)
    assert "waktu" in str(error.value).lower()


@pytest.mark.parametrize("timeout", [0, -1, True, "180"])
def test_generate_image_rejects_invalid_timeout(timeout):
    with pytest.raises(TrustAPIError, match="Timeout"):
        generate_image("prompt", "key", timeout_s=timeout)


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"data": []},
        {"data": [{}]},
        {"data": [{"b64_json": "%%%invalid%%%"}]},
    ],
)
def test_rejects_malformed_image_payload(payload):
    with pytest.raises(TrustAPIError):
        decode_image_response(payload)


@pytest.mark.parametrize("payload", [{"data": None}, {"data": "not-a-list"}, {"data": ["not-a-dict"]}])
def test_rejects_payload_with_invalid_data_shape(payload):
    with pytest.raises(TrustAPIError, match="data gambar"):
        decode_image_response(payload)


def test_rejects_non_image_url_response():
    def fake_get(*args, **kwargs):
        return FakeResponse(content=b"not image", headers={"Content-Type": "text/html"})

    with pytest.raises(TrustAPIError, match="tipe konten"):
        decode_image_response({"data": [{"url": "https://example.test/x"}]}, get_fn=fake_get)


def test_rejects_oversized_url_response():
    def fake_get(*args, **kwargs):
        return FakeResponse(
            content=b"x",
            headers={"Content-Type": "image/png", "Content-Length": str(20 * 1024 * 1024 + 1)},
        )

    with pytest.raises(TrustAPIError, match="terlalu besar"):
        decode_image_response({"data": [{"url": "https://example.test/x"}]}, get_fn=fake_get)


def test_rejects_invalid_image_bytes():
    with pytest.raises(TrustAPIError, match="rusak"):
        decode_image_response(
            {"data": [{"b64_json": base64.b64encode(b"not-an-image").decode()}]}
        )


def test_rejects_non_https_and_local_image_urls_before_download():
    called = False

    def fake_get(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("Tidak boleh dipanggil")

    for url in ("http://images.example/x.png", "https://127.0.0.1/x.png"):
        with pytest.raises(TrustAPIError, match="URL gambar"):
            decode_image_response({"data": [{"url": url}]}, get_fn=fake_get)
    assert called is False


def test_rejects_non_text_image_url_before_download():
    with pytest.raises(TrustAPIError, match="URL gambar"):
        decode_image_response({"data": [{"url": 123}]}, get_fn=lambda *args, **kwargs: pytest.fail())


def test_url_download_disables_redirects_and_streams_with_limit(monkeypatch):
    monkeypatch.setattr("trust_client.MAX_IMAGE_BYTES", 50)
    seen = {}

    def fake_get(url, **kwargs):
        seen.update(kwargs)
        return FakeResponse(
            content=b"x" * 51,
            headers={"Content-Type": "image/png"},
        )

    with pytest.raises(TrustAPIError, match="terlalu besar"):
        decode_image_response(
            {"data": [{"url": "https://images.example/x.png"}]}, get_fn=fake_get
        )
    assert seen["stream"] is True
    assert seen["allow_redirects"] is False


def test_redirect_response_is_rejected():
    def fake_get(*args, **kwargs):
        return FakeResponse(status_code=302, headers={"Location": "http://127.0.0.1/x"})

    with pytest.raises(TrustAPIError, match="(?i)pengalihan"):
        decode_image_response(
            {"data": [{"url": "https://images.example/x.png"}]}, get_fn=fake_get
        )


def test_decompression_bomb_becomes_safe_api_error(monkeypatch):
    def explode(*args, **kwargs):
        raise Image.DecompressionBombError("too many pixels")

    monkeypatch.setattr("trust_client.Image.open", explode)
    with pytest.raises(TrustAPIError, match="(?i)dimensi"):
        decode_image_response(
            {"data": [{"b64_json": base64.b64encode(png_bytes()).decode()}]}
        )


def test_generate_image_rejects_oversized_post_before_json_parse(monkeypatch):
    monkeypatch.setattr("trust_client.MAX_API_RESPONSE_BYTES", 80)
    expected = png_bytes()
    payload = {"data": [{"b64_json": base64.b64encode(expected).decode()}]}
    raw = json.dumps(payload).encode()

    def fake_post(*args, **kwargs):
        return FakeResponse(
            content=raw,
            headers={"Content-Type": "application/json"},
        )

    with pytest.raises(TrustAPIError, match="terlalu besar"):
        generate_image("prompt", "key", post_fn=fake_post)


def test_generate_image_streams_post_response():
    seen = {}
    expected = png_bytes()
    raw = json.dumps(
        {"data": [{"b64_json": base64.b64encode(expected).decode()}]}
    ).encode()

    def fake_post(*args, **kwargs):
        seen.update(kwargs)
        return FakeResponse(content=raw, headers={"Content-Type": "application/json"})

    assert generate_image("prompt", "key", post_fn=fake_post) == expected
    assert seen["stream"] is True


def test_bynara_uses_separate_negative_prompt_and_key():
    seen = {}
    image = png_bytes()

    def fake_post(url, **kwargs):
        seen.update(url=url, **kwargs)
        return FakeResponse(payload={"data": [{"b64_json": base64.b64encode(image).decode()}]})

    assert generate_bynara_image("Gambar kandang", "kabut", "NARA-KEY", post_fn=fake_post) == image
    assert seen["url"] == "https://api-images.bynara.id/v1/images/generations"
    assert seen["headers"]["Authorization"] == "Bearer NARA-KEY"
    assert seen["json"] == {
        "model": "gpt-image-2", "prompt": "Gambar kandang", "negative_prompt": "kabut",
        "n": 1, "size": "2048x2048", "quality": "medium", "response_format": "b64_json",
    }
    assert seen["stream"] is True
    assert seen["timeout"] == 180


def test_bynara_missing_model_or_key_never_sends(monkeypatch):
    monkeypatch.setattr("trust_client.st.secrets", {
        "NARA_ENDPOINT": "https://api-images.bynara.id/v1/images/generations",
        "NARA_MODEL": "",
    })
    with pytest.raises(TrustAPIError, match="NARA_MODEL"):
        generate_bynara_image("prompt", "", "key", post_fn=lambda *a, **k: pytest.fail())
    with pytest.raises(TrustAPIError, match="NARA_API_KEY"):
        generate_bynara_image("prompt", "", "", post_fn=lambda *a, **k: pytest.fail())


@pytest.mark.parametrize("endpoint", [
    "", "http://api-images.bynara.id/v1/images/generations",
    "https://localhost/v1/images/generations",
    "https://127.0.0.1/v1/images/generations",
    "https://user:password@api-images.bynara.id/v1/images/generations",
    "https://api-images.bynara.id:8443/v1/images/generations",
    123,
])
def test_bynara_rejects_missing_or_unsafe_endpoint_before_request(monkeypatch, endpoint):
    monkeypatch.setattr("trust_client.st.secrets", {
        "NARA_ENDPOINT": endpoint, "NARA_MODEL": "gpt-image-2",
    })
    with pytest.raises(TrustAPIError, match="NARA_ENDPOINT"):
        generate_bynara_image("prompt", "", "key", post_fn=lambda *a, **k: pytest.fail())


def test_bynara_uses_endpoint_from_secrets(monkeypatch):
    monkeypatch.setattr("trust_client.st.secrets", {
        "NARA_ENDPOINT": "https://images.example/v1/images/generations",
        "NARA_MODEL": "gpt-image-2",
    })
    seen = []
    image = png_bytes()

    def fake_post(url, **kwargs):
        seen.append(url)
        return FakeResponse(payload={"data": [{"b64_json": base64.b64encode(image).decode()}]})

    assert generate_bynara_image("prompt", "", "key", post_fn=fake_post) == image
    assert seen == ["https://images.example/v1/images/generations"]


def test_bynara_http_error_does_not_echo_response_or_key():
    with pytest.raises(TrustAPIError) as exc:
        generate_bynara_image("private prompt", "", "NARA-KEY", post_fn=lambda *a, **k:
            FakeResponse(status_code=400, payload={"error": "private prompt NARA-KEY"}))
    assert "HTTP 400" in str(exc.value)
    assert "NARA-KEY" not in str(exc.value)
    assert "private prompt" not in str(exc.value)


def test_bynara_http_400_shows_only_allowlisted_validation_metadata():
    response = FakeResponse(status_code=400, payload={"error": {
        "type": "validation_error", "param": "size", "request_id": "req_SAFE123",
        "message": "private prompt NARA-KEY",
    }})
    with pytest.raises(TrustAPIError) as exc:
        generate_bynara_image("private prompt", "", "NARA-KEY", post_fn=lambda *a, **k: response)
    message = str(exc.value)
    assert "HTTP 400" in message
    assert "parameter: size" in message
    assert "req_SAFE123" in message
    assert "private prompt" not in message
    assert "NARA-KEY" not in message


def test_trust_only_service_failures_are_fallback_eligible():
    for status, expected in ((400, TrustServiceError), (503, TrustServiceError),
                             (401, TrustAPIError), (402, TrustAPIError), (429, TrustAPIError)):
        with pytest.raises(expected) as exc:
            generate_image("prompt", "key", post_fn=lambda *a, **k:
                FakeResponse(status_code=status, payload={"error": "failed"}))
        assert isinstance(exc.value, TrustServiceError) is (status in (400, 503))


def test_trust_connection_error_is_fallback_eligible_but_timeout_is_not():
    def fail_connection(*args, **kwargs):
        raise requests.ConnectionError("offline")

    def fail_timeout(*args, **kwargs):
        raise requests.Timeout("unknown outcome")

    with pytest.raises(TrustServiceError):
        generate_image("prompt", "key", post_fn=fail_connection)
    with pytest.raises(TrustAPIError) as exc:
        generate_image("prompt", "key", post_fn=fail_timeout)
    assert not isinstance(exc.value, TrustServiceError)


def test_bynara_rejects_oversized_response_before_json_parse(monkeypatch):
    monkeypatch.setattr("trust_client.MAX_API_RESPONSE_BYTES", 80)
    response = FakeResponse(payload={"data": [{"b64_json": base64.b64encode(png_bytes()).decode()}]})
    with pytest.raises(TrustAPIError, match="terlalu besar"):
        generate_bynara_image("prompt", "", "key", post_fn=lambda *args, **kwargs: response)
