import base64
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from app import get_nara_api_key


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def test_nara_key_comes_only_from_secrets(monkeypatch):
    monkeypatch.setenv("NARA_API_KEY", "env-key-not-used")
    monkeypatch.setattr("app.st.secrets", {"NARA_API_KEY": "  secret-key  "})
    assert get_nara_api_key() == "secret-key"
    monkeypatch.setattr("app.st.secrets", {"NARA_API_KEY": ""})
    assert get_nara_api_key() is None


def test_app_starts_and_renders_primary_controls():
    app = AppTest.from_file(APP_PATH).run(timeout=10)
    assert not app.exception
    assert app.title[0].value == "Generator Konsep Kandang Close House"
    assert len(app.number_input) == 2
    assert app.number_input[0].value == 32.0
    assert app.number_input[1].value == 8.0
    assert app.info[0].value.startswith("Luas: **256 m²**")
    assert app.button[0].label == "Buat gambar konsep"
    assert app.text_area[0].value.startswith("Buat gambar konsep kandang close house")
    assert "Sapi" in app.selectbox[0].options
    assert "Lainnya" in app.selectbox[0].options
    assert "kesejahteraan hewan" in app.text_area[0].value
    assert "Anatomi ternak keliru" in app.text_area[1].value
    assert "Render hiperrealistis" in app.selectbox[1].options
    assert "tidak membuktikan kepatuhan kesejahteraan hewan" in app.warning[0].value
    assert any("Rencana awal yang realistis" in header.value for header in app.subheader)
    assert any("Lihat brief perencanaan" in item.label for item in app.expander)


def test_summary_and_schematic_follow_input_changes():
    app = AppTest.from_file(APP_PATH).run(timeout=10)
    app.number_input[0].set_value(40.0).run(timeout=10)
    assert app.info[0].value.startswith("Luas: **320 m²**")
    assert any("320 m²" in item.value and "40 m panjang" in item.value for item in app.markdown)
    app.multiselect[0].set_value([]).run(timeout=10)
    assert any("Udara masuk*" in item.value and "Udara keluar*" in item.value for item in app.markdown)


def test_schematic_escapes_custom_livestock_name():
    app = AppTest.from_file(APP_PATH).run(timeout=10)
    app.selectbox[0].set_value("Lainnya").run(timeout=10)
    app.text_input[0].set_value("Sapi <uji>").run(timeout=10)
    assert any("Sapi &lt;uji&gt;" in item.value for item in app.markdown)
    assert not any("<small>Sapi <uji></small>" in item.value for item in app.markdown)


def test_prompt_edits_survive_rerun_and_reset_on_livestock_change(monkeypatch):
    monkeypatch.delenv("TRUST_API_KEY", raising=False)
    monkeypatch.setattr("streamlit.secrets", {})
    app = AppTest.from_file(APP_PATH).run(timeout=10)
    app.text_area[0].set_value("  Gambar kandang khusus  ").run(timeout=10)
    app.text_area[1].set_value("  Hindari kabut  ").run(timeout=10)
    assert app.text_area[0].value == "  Gambar kandang khusus  "
    assert app.text_area[1].value == "  Hindari kabut  "
    app.button[0].click().run(timeout=10)
    assert app.code[0].value == "Gambar kandang khusus\n\nHindari dalam gambar (negative prompt): Hindari kabut"
    app.selectbox[0].set_value("Sapi").run(timeout=10)
    assert "untuk Sapi" in app.text_area[0].value
    assert "Gambar kandang khusus" not in app.text_area[0].value
    assert "Hindari kabut" not in app.text_area[1].value
    assert "nipple" not in app.text_area[0].value.lower()


def test_hyperrealistic_style_resets_negative_prompt():
    app = AppTest.from_file(APP_PATH).run(timeout=10)
    app.text_area[1].set_value("Tanpa kabut").run(timeout=10)
    app.selectbox[1].set_value("Render hiperrealistis").run(timeout=10)
    assert "seperti foto arsitektur" in app.text_area[0].value
    assert "Tampilan kartun" in app.text_area[1].value
    assert "Tanpa kabut" not in app.text_area[1].value
    app.selectbox[1].set_value("Render realistis").run(timeout=10)
    assert "Tampilan kartun" not in app.text_area[1].value


def test_generation_sends_edited_prompt(monkeypatch):
    monkeypatch.setenv("TRUST_API_KEY", "test-key")
    monkeypatch.setattr("streamlit.secrets", {"TRUST_API_KEY": "cloud-test-key"})
    sent = []

    def fake_generate(prompt, api_key):
        sent.append((prompt, api_key))
        return base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/"
            "lXcAAAAASUVORK5CYII="
        )

    monkeypatch.setattr("trust_client.generate_image", fake_generate)
    monkeypatch.setattr("trust_client.generate_bynara_image", lambda *args: pytest.fail(
        "Bynara tidak boleh dipanggil jika Trust berhasil"
    ))
    app = AppTest.from_file(APP_PATH).run(timeout=10)
    app.text_area[0].set_value("Gambar kandang sapi khusus").run(timeout=10)
    app.text_area[1].set_value("Tanpa kabut dan tanpa kartun").run(timeout=10)
    app.button[0].click().run(timeout=10)
    assert not app.exception
    expected = "Gambar kandang sapi khusus\n\nHindari dalam gambar (negative prompt): Tanpa kabut dan tanpa kartun"
    assert sent == [(expected, "cloud-test-key")]
    assert app.code[0].value == expected


@pytest.mark.parametrize("failure", ["HTTP 503", "Koneksi Trust gagal"])
def test_trust_failure_uses_bynara_with_separate_negative_prompt(monkeypatch, failure):
    from trust_client import TrustServiceError

    monkeypatch.setenv("TRUST_API_KEY", "trust-key")
    monkeypatch.setattr("streamlit.secrets", {"NARA_API_KEY": "nara-key"})
    sent = []
    def fail_trust(prompt, api_key):
        sent.append(("Trust", prompt, api_key))
        raise TrustServiceError(failure)
    def succeed_nara(prompt, negative_prompt, api_key):
        sent.append(("Bynara", prompt, negative_prompt, api_key))
        return base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/"
            "lXcAAAAASUVORK5CYII="
        )
    monkeypatch.setattr("trust_client.generate_image", fail_trust)
    monkeypatch.setattr("trust_client.generate_bynara_image", succeed_nara)
    app = AppTest.from_file(APP_PATH).run(timeout=10)
    app.text_area[0].set_value("Gambar sapi").run(timeout=10)
    app.text_area[1].set_value("Kabut").run(timeout=10)
    app.button[0].click().run(timeout=10)
    assert not app.exception
    assert sent == [
        ("Trust", "Gambar sapi\n\nHindari dalam gambar (negative prompt): Kabut", "trust-key"),
        ("Bynara", "Gambar sapi", "Kabut", "nara-key"),
    ]
    assert "Bynara" in app.success[0].value
    assert any("Mencoba Bynara" in message.value for message in app.info)
    assert any(failure in message.value for message in app.warning)


def test_trust_auth_error_does_not_trigger_bynara(monkeypatch):
    from trust_client import TrustAPIError

    monkeypatch.setenv("TRUST_API_KEY", "trust-key")
    monkeypatch.setattr("streamlit.secrets", {"NARA_API_KEY": "nara-key"})
    monkeypatch.setattr("trust_client.generate_image", lambda *args: (_ for _ in ()).throw(
        TrustAPIError("API key Trust tidak sah atau tidak berizin.")))
    monkeypatch.setattr("trust_client.generate_bynara_image", lambda *args: (_ for _ in ()).throw(
        AssertionError("Bynara tidak boleh dipanggil")))
    app = AppTest.from_file(APP_PATH).run(timeout=10)
    app.button[0].click().run(timeout=10)
    assert not app.exception
    assert "API key Trust" in app.error[0].value


def test_trust_http_400_does_not_trigger_bynara(monkeypatch):
    from trust_client import TrustAPIError

    monkeypatch.setenv("TRUST_API_KEY", "trust-key")
    monkeypatch.setattr("streamlit.secrets", {"NARA_API_KEY": "nara-key"})
    monkeypatch.setattr("trust_client.generate_image", lambda *args: (_ for _ in ()).throw(
        TrustAPIError("Layanan menolak permintaan (HTTP 400).")))
    monkeypatch.setattr("trust_client.generate_bynara_image", lambda *args: (_ for _ in ()).throw(
        AssertionError("Bynara tidak boleh dipanggil")))
    app = AppTest.from_file(APP_PATH).run(timeout=10)
    app.button[0].click().run(timeout=10)
    assert not app.exception
    assert "HTTP 400" in app.error[0].value
    assert not any("Mencoba Bynara" in message.value for message in app.info)


def test_trust_failure_without_bynara_key_is_clear(monkeypatch):
    from trust_client import TrustServiceError

    monkeypatch.setenv("TRUST_API_KEY", "trust-key")
    monkeypatch.setattr("streamlit.secrets", {})
    monkeypatch.setattr("trust_client.generate_image", lambda *args: (_ for _ in ()).throw(
        TrustServiceError("HTTP 503")))
    app = AppTest.from_file(APP_PATH).run(timeout=10)
    app.button[0].click().run(timeout=10)
    assert not app.exception
    assert "NARA_API_KEY" in app.error[0].value


def test_oversized_combined_prompt_is_not_sent(monkeypatch):
    monkeypatch.setenv("TRUST_API_KEY", "test-key")
    sent = []
    monkeypatch.setattr("trust_client.generate_image", lambda prompt, api_key: sent.append(prompt))
    app = AppTest.from_file(APP_PATH).run(timeout=10)
    app.text_area[0].set_value("a" * 8000).run(timeout=10)
    app.button[0].click().run(timeout=10)
    assert not sent
    assert any("8000 karakter" in error.value for error in app.error)
    assert not app.code


def test_other_livestock_requires_name_before_generation(monkeypatch):
    monkeypatch.delenv("TRUST_API_KEY", raising=False)
    monkeypatch.setattr("streamlit.secrets", {})
    app = AppTest.from_file(APP_PATH).run(timeout=10)
    app.selectbox[0].set_value("Lainnya").run(timeout=10)
    app.button[0].click().run(timeout=10)
    assert any("Isi jenis ternak lain" in error.value for error in app.error)
    assert not app.code
    app.text_input[0].set_value("Kerbau").run(timeout=10)
    assert "untuk Kerbau" in app.text_area[0].value


def test_generate_without_key_shows_safe_configuration_error(monkeypatch):
    monkeypatch.delenv("TRUST_API_KEY", raising=False)
    monkeypatch.setattr("streamlit.secrets", {})
    app = AppTest.from_file(APP_PATH)
    app.run(timeout=10)
    app.button[0].click().run(timeout=10)
    assert not app.exception
    assert "TRUST_API_KEY belum dikonfigurasi" in app.error[0].value
    assert "App settings → Secrets" in app.error[0].value
    assert len(app.code) == 1
