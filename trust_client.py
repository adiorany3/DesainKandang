"""Klien aman untuk endpoint generasi gambar Trust."""

from __future__ import annotations

import base64
import binascii
import io
import ipaddress
import json
import re
import socket
from collections.abc import Callable
from typing import Any
from urllib.parse import urlsplit

import requests
import streamlit as st
from PIL import Image, UnidentifiedImageError

MAX_IMAGE_BYTES = 20 * 1024 * 1024
MAX_API_RESPONSE_BYTES = 28 * 1024 * 1024
MAX_IMAGE_PIXELS = 16_000_000
CHUNK_BYTES = 64 * 1024
MAX_ERROR_RESPONSE_BYTES = 8192


class TrustAPIError(RuntimeError):
    """Kesalahan publik yang aman ditampilkan pada antarmuka."""


class TrustServiceError(TrustAPIError):
    """Kegagalan Trust yang boleh dialihkan ke penyedia cadangan."""


def _read_limited(response: Any, maximum: int, label: str) -> bytes:
    """Baca respons streaming tanpa pernah melewati batas byte."""
    try:
        announced = int(response.headers.get("Content-Length", "0"))
    except (TypeError, ValueError):
        announced = 0
    if announced > maximum:
        raise TrustAPIError(f"{label} terlalu besar.")

    output = bytearray()
    for chunk in response.iter_content(chunk_size=CHUNK_BYTES):
        if not chunk:
            continue
        if len(output) + len(chunk) > maximum:
            raise TrustAPIError(f"{label} terlalu besar.")
        output.extend(chunk)
    return bytes(output)


def _validate_public_https_url(url: str) -> None:
    """Tolak URL non-HTTPS, kredensial, port khusus, dan alamat nonpublik."""
    try:
        if not isinstance(url, str):
            raise ValueError("URL bukan teks")
        parsed = urlsplit(url)
        host = parsed.hostname
        port = parsed.port
    except (TypeError, ValueError) as exc:
        raise TrustAPIError("URL gambar dari API tidak valid.") from exc
    if parsed.scheme != "https" or not host or parsed.username or parsed.password:
        raise TrustAPIError("URL gambar harus HTTPS dan tidak memuat kredensial.")
    if port not in (None, 443):
        raise TrustAPIError("URL gambar memakai port yang tidak diizinkan.")

    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)}
    except socket.gaierror as exc:
        raise TrustAPIError("Host URL gambar tidak dapat ditemukan.") from exc
    if not addresses:
        raise TrustAPIError("Host URL gambar tidak memiliki alamat yang valid.")
    try:
        if any(not ipaddress.ip_address(address).is_global for address in addresses):
            raise TrustAPIError("URL gambar mengarah ke jaringan yang tidak diizinkan.")
    except ValueError as exc:
        raise TrustAPIError("Alamat host URL gambar tidak valid.") from exc


def _get_endpoint() -> str:
    """Ambil endpoint konfigurasi dan pastikan hanya HTTPS standar yang dipakai."""
    return _get_configured_endpoint("ENDPOINT")


def _get_configured_endpoint(name: str) -> str:
    """Validasi URL endpoint yang ditetapkan pada secrets sebelum mengirim kredensial."""
    try:
        configured = st.secrets.get(name, "")
        endpoint = configured.strip() if isinstance(configured, str) else ""
    except (FileNotFoundError, KeyError):
        endpoint = ""
    try:
        parsed = urlsplit(endpoint)
        valid = (
            parsed.scheme == "https"
            and bool(parsed.hostname)
            and not parsed.username
            and not parsed.password
            and parsed.port in (None, 443)
            and parsed.hostname != "localhost"
            and not (
                parsed.hostname is not None
                and _is_nonpublic_ip(parsed.hostname)
            )
        )
    except ValueError:
        valid = False
    if not valid:
        raise TrustAPIError(
            f"{name} harus berupa URL HTTPS publik yang valid di Streamlit Secrets "
            "(App settings → Secrets di Cloud; .streamlit/secrets.toml secara lokal)."
        )
    return endpoint


def _is_nonpublic_ip(host: str) -> bool:
    try:
        return not ipaddress.ip_address(host).is_global
    except ValueError:
        return False


def _get_model() -> str:
    """Ambil nama model dari Streamlit Secrets, tanpa fallback tersembunyi."""
    try:
        configured = st.secrets.get("MODEL", "")
    except (FileNotFoundError, KeyError):
        configured = ""
    model = configured.strip() if isinstance(configured, str) else ""
    if not model:
        raise TrustAPIError("MODEL harus diisi di Streamlit Secrets (App settings → Secrets di Cloud).")
    return model


def _validation_error_detail(response: Any) -> str:
    """Tampilkan hanya metadata error yang aman; jangan tampilkan pesan mentah API."""
    try:
        raw = _read_limited(response, MAX_ERROR_RESPONSE_BYTES, "Respons kesalahan API")
        payload = json.loads(raw)
    except (TrustAPIError, ValueError, TypeError, UnicodeDecodeError):
        return ""
    if not isinstance(payload, dict) or not isinstance(payload.get("error"), dict):
        return ""
    error = payload["error"]
    details = []
    if isinstance(error.get("type"), str) and error["type"] in {"validation_error", "bad_request"}:
        details.append("jenis: validasi permintaan")
    if isinstance(error.get("param"), str) and error["param"] in {"model", "prompt", "size", "quality", "n"}:
        details.append(f"parameter: {error['param']}")
    request_id = error.get("request_id")
    if isinstance(request_id, str) and re.fullmatch(r"req_[A-Za-z0-9_-]{1,64}", request_id):
        details.append(f"ID permintaan: {request_id}")
    return " (" + "; ".join(details) + ")" if details else ""


def _validate_png(image_bytes: bytes) -> bytes:
    if not image_bytes:
        raise TrustAPIError("Data gambar kosong.")
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise TrustAPIError("Data gambar terlalu besar (maksimum 20 MiB).")
    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            if image.format not in {"PNG", "JPEG", "WEBP"}:
                raise TrustAPIError("Format gambar dari API tidak didukung.")
            width, height = image.size
            if width <= 0 or height <= 0 or width * height > MAX_IMAGE_PIXELS:
                raise TrustAPIError("Dimensi gambar terlalu besar atau tidak valid.")
            image.load()
            if image.format == "PNG":
                return image_bytes
            output = io.BytesIO()
            image.save(output, format="PNG")
            if output.tell() > MAX_IMAGE_BYTES:
                raise TrustAPIError("Data gambar terlalu besar (maksimum 20 MiB).")
            return output.getvalue()
    except Image.DecompressionBombError as exc:
        raise TrustAPIError("Dimensi gambar terlalu besar untuk diproses dengan aman.") from exc
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise TrustAPIError("Berkas gambar dari API rusak atau tidak dapat dibaca.") from exc


def decode_image_response(
    payload: dict[str, Any],
    get_fn: Callable[..., Any] = requests.get,
    timeout_s: int = 180,
) -> bytes:
    """Dekode varian b64_json atau URL menjadi PNG tervalidasi."""
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise TrustAPIError("Respons API tidak memuat data gambar.")
    try:
        item = payload["data"][0]
    except IndexError as exc:
        raise TrustAPIError("Respons API tidak memuat data gambar.") from exc
    if not isinstance(item, dict):
        raise TrustAPIError("Respons API tidak memuat data gambar yang valid.")

    if item.get("b64_json"):
        encoded = item["b64_json"]
        if not isinstance(encoded, str) or len(encoded) > (MAX_IMAGE_BYTES * 4 // 3) + 8:
            raise TrustAPIError("Data gambar base64 terlalu besar atau tidak valid.")
        try:
            image_bytes = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError, TypeError) as exc:
            raise TrustAPIError("Data gambar base64 dari API tidak valid.") from exc
        return _validate_png(image_bytes)

    if item.get("url"):
        url = item["url"]
        if not isinstance(url, str):
            raise TrustAPIError("URL gambar dari API tidak valid.")
        _validate_public_https_url(url)
        try:
            with get_fn(
                url,
                timeout=timeout_s,
                stream=True,
                allow_redirects=False,
            ) as response:
                if 300 <= response.status_code < 400:
                    raise TrustAPIError("Pengalihan URL gambar tidak diizinkan.")
                if response.status_code >= 400:
                    raise TrustAPIError("Server gambar menolak permintaan unduhan.")
                content_type = response.headers.get("Content-Type", "").lower()
                if not content_type.startswith("image/"):
                    raise TrustAPIError("Respons URL memiliki tipe konten yang bukan gambar.")
                image_bytes = _read_limited(response, MAX_IMAGE_BYTES, "Data gambar")
        except requests.Timeout as exc:
            raise TrustAPIError("Waktu unduh gambar habis. Silakan coba lagi.") from exc
        except requests.RequestException as exc:
            raise TrustAPIError("Gagal mengunduh gambar dari API.") from exc
        return _validate_png(image_bytes)

    raise TrustAPIError("Respons API tidak memuat base64 atau URL gambar.")


def generate_image(
    prompt: str,
    api_key: str,
    timeout_s: int = 180,
    post_fn: Callable[..., Any] = requests.post,
) -> bytes:
    """Kirim permintaan generasi ke Trust dan kembalikan PNG tervalidasi."""
    if not isinstance(api_key, str) or not api_key.strip():
        raise TrustAPIError("API key Trust belum dikonfigurasi.")
    if isinstance(timeout_s, bool) or not isinstance(timeout_s, (int, float)) or timeout_s <= 0:
        raise TrustAPIError("Timeout permintaan API harus berupa angka positif.")
    endpoint = _get_endpoint()
    model = _get_model()

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": model,
        "prompt": prompt,
        "size": "1024x1024",
        "quality": "medium",
        "n": 1,
    }
    try:
        with post_fn(
            endpoint,
            headers=headers,
            json=body,
            timeout=timeout_s,
            stream=True,
        ) as response:
            if response.status_code == 401:
                raise TrustAPIError("API key Trust tidak sah atau tidak berizin.")
            if response.status_code == 402:
                raise TrustAPIError("Kredit API tidak mencukupi untuk membuat gambar.")
            if response.status_code == 429:
                raise TrustAPIError("Batas permintaan API tercapai. Tunggu lalu coba lagi.")
            if response.status_code == 400:
                detail = _validation_error_detail(response)
                raise TrustServiceError(
                    "Layanan menolak permintaan (HTTP 400)"
                    f"{detail}. Periksa parameter MODEL, prompt, size, quality, "
                    "dan n serta ketentuan layanan; gunakan ID permintaan untuk dukungan penyedia."
                )
            if response.status_code >= 500:
                raise TrustServiceError(f"Layanan Trust gagal dengan status HTTP {response.status_code}.")
            if response.status_code >= 400:
                raise TrustAPIError(
                    f"Layanan Trust gagal dengan status HTTP {response.status_code}."
                )
            raw_payload = _read_limited(
                response, MAX_API_RESPONSE_BYTES, "Respons API"
            )
    except requests.Timeout as exc:
        raise TrustAPIError("Waktu permintaan habis. Silakan coba lagi.") from exc
    except requests.ConnectionError as exc:
        raise TrustServiceError("Koneksi ke layanan Trust gagal. Periksa jaringan.") from exc
    except requests.RequestException as exc:
        raise TrustAPIError("Koneksi ke layanan Trust gagal. Periksa jaringan.") from exc

    try:
        payload = json.loads(raw_payload)
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError) as exc:
        raise TrustAPIError("Respons API bukan JSON yang valid.") from exc
    if not isinstance(payload, dict):
        raise TrustAPIError("Format respons API tidak valid.")
    return decode_image_response(payload, timeout_s=timeout_s)


def generate_bynara_image(
    prompt: str,
    negative_prompt: str,
    api_key: str,
    timeout_s: int = 180,
    post_fn: Callable[..., Any] = requests.post,
) -> bytes:
    """Kirim satu permintaan gambar cadangan dan validasi PNG hasilnya."""
    if not isinstance(api_key, str) or not api_key.strip():
        raise TrustAPIError("NARA_API_KEY belum dikonfigurasi.")
    if isinstance(timeout_s, bool) or not isinstance(timeout_s, (int, float)) or timeout_s <= 0:
        raise TrustAPIError("Timeout permintaan API harus berupa angka positif.")
    endpoint = _get_configured_endpoint("NARA_ENDPOINT")
    try:
        configured = st.secrets.get("NARA_MODEL", "")
    except (FileNotFoundError, KeyError):
        configured = ""
    model = configured.strip() if isinstance(configured, str) else ""
    if not model:
        raise TrustAPIError("NARA_MODEL harus diisi di Streamlit Secrets (App settings → Secrets di Cloud).")

    body = {
        "model": model,
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "n": 1,
        "size": "2048x2048",
        "quality": "medium",
        "response_format": "b64_json",
    }
    try:
        with post_fn(
            endpoint,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=body,
            timeout=timeout_s,
            stream=True,
        ) as response:
            if response.status_code >= 400:
                if response.status_code == 400:
                    detail = _validation_error_detail(response)
                    raise TrustAPIError(
                        "Layanan Bynara gagal dengan status HTTP 400" + detail + ". "
                        "Periksa model dan parameter permintaan yang didukung oleh penyedia."
                    )
                raise TrustAPIError(f"Layanan Bynara gagal dengan status HTTP {response.status_code}.")
            raw = _read_limited(response, MAX_API_RESPONSE_BYTES, "Respons API")
    except requests.Timeout as exc:
        raise TrustAPIError("Waktu permintaan Bynara habis. Silakan coba lagi.") from exc
    except requests.RequestException as exc:
        raise TrustAPIError("Koneksi ke layanan Bynara gagal. Periksa jaringan.") from exc
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError) as exc:
        raise TrustAPIError("Respons Bynara bukan JSON yang valid.") from exc
    if not isinstance(payload, dict):
        raise TrustAPIError("Format respons Bynara tidak valid.")
    return decode_image_response(payload, timeout_s=timeout_s)
