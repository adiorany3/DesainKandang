import pytest

from app import (
    FEATURE_OPTIONS, LIVESTOCK_OPTIONS, MAX_PROMPT_CHARS, NEGATIVE_HYPERREALISM,
    NEGATIVE_PROMPT, STYLE_OPTIONS, build_prompt, calculate_area, compose_image_prompt,
    build_planning_brief, get_api_key, validate_dimensions, validate_prompt,
)


@pytest.mark.parametrize(
    ("length", "width", "area"),
    [(32, 8, 256.0), (10, 12, 120.0), (1.25, 2, 2.5)],
)
def test_calculate_area(length, width, area):
    assert calculate_area(length, width) == area


@pytest.mark.parametrize(
    ("length", "width"),
    [
        ("32", 8),
        (32, None),
        (True, 8),
        (0, 8),
        (-2, 3),
        (201, 3),
        (float("nan"), 2),
        (3, float("inf")),
    ],
)
def test_reject_invalid_dimensions(length, width):
    with pytest.raises(ValueError):
        validate_dimensions(length, width)


@pytest.mark.parametrize(("length", "width"), [(1, 1), (200, 200)])
def test_accept_dimension_boundaries(length, width):
    validate_dimensions(length, width)


def test_prompt_includes_dimensions_area_features_and_long_form():
    prompt = build_prompt(
        32,
        8,
        "Ayam broiler",
        ["Cooling pad", "Exhaust fan"],
        "Sketsa pensil arsitektural",
    )
    assert "32" in prompt and "8" in prompt and "256" in prompt
    assert "Cooling pad" in prompt and "Exhaust fan" in prompt
    assert "memanjang" in prompt.lower()
    assert "persegi" in prompt.lower()


def test_prompt_places_ventilation_without_impossible_end_doors():
    prompt = build_prompt(
        32, 8, "Ayam broiler", ["Cooling pad", "Exhaust fan", "Zona biosekuriti"],
        "Render realistis",
    )
    assert "ujung berlawanan" in prompt
    assert "panel selulosa sarang lebah" in prompt and "talang air" in prompt
    assert "kipas aksial berbingkai" in prompt and "menembus dinding" in prompt
    assert "bukan lubang pada kandang jadi" in prompt
    assert "ujung panah harus tepat menyentuh panel" in prompt
    assert "bukan kipas, pintu, atap" in prompt
    assert "hilangkan tanda dan panah" in prompt
    assert "bukan pintu" in prompt
    assert "pintu akses" in prompt
    assert "di LUAR" in prompt
    assert "di dalam area ternak" in prompt
    assert "pintu luar" in prompt and "pintu dalam" in prompt
    assert "fotorealistis" in prompt

def test_prompt_places_feed_water_and_biosecurity_in_distinct_areas():
    prompt = build_prompt(
        32, 8, "Ayam broiler",
        ["Cooling pad", "Exhaust fan", "Jalur pakan otomatis", "Nipple drinker", "Zona biosekuriti"],
        "Render realistis",
    )
    assert "pan feeder" in prompt and "silo di luar kandang" in prompt
    assert "pipa air" in prompt and "bukan keran dinding" in prompt
    assert "ruang masuk kecil tertutup" in prompt and "di LUAR" in prompt
    assert "potongan atap" in prompt
    assert "setiap fitur yang dipilih tampak" in prompt
    assert "peralatan ternak di dalam" in prompt and "perangkat eksterior di luar" in prompt
    assert "Pisahkan jalur pakan dan jalur minum" in prompt
    assert "sekam kering" in prompt


@pytest.mark.parametrize(
    ("livestock", "expected"),
    [("Ayam petelur", "sarang bertelur"), ("Bebek pedaging", "bukan di kolam air")],
)
def test_prompt_uses_consistent_livestock_housing(livestock, expected):
    prompt = build_prompt(32, 8, livestock, ["Nipple drinker"], "Render realistis")
    assert expected in prompt
    assert "sejajar sumbu panjang kandang" in prompt
    assert "Pisahkan jalur pakan dan jalur minum" not in prompt

@pytest.mark.parametrize(
    ("livestock", "expected"),
    [("Sapi", "tidak licin"), ("Kambing", "area kering"), ("Domba", "area kering")],
)
def test_prompt_uses_non_poultry_equipment(livestock, expected):
    prompt = build_prompt(
        32, 8, livestock, ["Jalur pakan otomatis", "Tempat minum otomatis"],
        "Render realistis",
    )
    assert expected in prompt
    assert "palung pakan" in prompt and "palung minum" in prompt
    assert "pan feeder" not in prompt and "sekam" not in prompt


@pytest.mark.parametrize(
    ("livestock", "expected"),
    [
        ("Ayam broiler", "litter kering"),
        ("Ayam petelur", "tenggeran"),
        ("Bebek pedaging", "membersihkan mata serta lubang hidung"),
        ("Sapi", "berbaring"),
        ("Kambing", "berinteraksi sosial"),
        ("Domba", "berinteraksi sosial"),
    ],
)
def test_prompt_includes_welfare_for_each_livestock(livestock, expected):
    prompt = build_prompt(32, 8, livestock, [], "Render realistis")
    assert "prinsip kesejahteraan hewan" in prompt
    assert "air minum bersih" in prompt
    assert "akses pemeriksaan" in prompt
    assert "Jangan menggambarkan ternak berdesakan" in prompt
    assert "sarana dasar pakan dan air" in prompt
    assert expected in prompt
    assert len(prompt) <= 8000


def test_other_livestock_gets_generic_welfare_without_species_assumptions():
    prompt = build_prompt(32, 8, "Lainnya", [], "Render realistis", "Kerbau")
    assert "prinsip kesejahteraan hewan" in prompt
    assert "Sesuaikan fasilitas dengan kebutuhan spesies" in prompt
    assert "tenggeran" not in prompt
    assert len(prompt) <= 8000


def test_prompt_supports_named_other_livestock():
    prompt = build_prompt(32, 8, "Lainnya", [], "Render realistis", "  Kerbau  ")
    assert "untuk Kerbau." in prompt
    assert "Bebek pedaging berada" not in prompt


@pytest.mark.parametrize("name", ["", " ", "x" * 61, "Sapi\nKambing"])
def test_prompt_rejects_invalid_other_livestock(name):
    with pytest.raises(ValueError):
        build_prompt(32, 8, "Lainnya", [], "Render realistis", name)


def test_prompt_rejects_invalid_argument_types():
    with pytest.raises(ValueError, match="(?i)fitur"):
        build_prompt(32, 8, "Sapi", None, "Render realistis")
    with pytest.raises(ValueError, match="jenis ternak lain"):
        build_prompt(32, 8, "Lainnya", [], "Render realistis", 123)


@pytest.mark.parametrize("prompt", ["", "  ", "x" * 8001, None, 123])
def test_prompt_rejects_empty_or_oversized_edits(prompt):
    with pytest.raises(ValueError):
        validate_prompt(prompt)


@pytest.mark.parametrize("value", [None, 123, ["teks"]])
def test_prompt_helpers_reject_non_text_input(value):
    with pytest.raises(ValueError):
        validate_prompt(value)
    with pytest.raises(ValueError):
        compose_image_prompt("Gambar sapi", value)


def test_build_prompt_rejects_invalid_feature_and_custom_livestock_types():
    with pytest.raises(ValueError):
        build_prompt(32, 8, "Sapi", "Exhaust fan", "Render realistis")
    with pytest.raises(ValueError):
        build_prompt(32, 8, "Lainnya", [], "Render realistis", 123)


def test_prompt_keeps_valid_edit():
    assert validate_prompt("  Gambar kandang sapi  ") == "Gambar kandang sapi"

@pytest.mark.parametrize("style", STYLE_OPTIONS)
def test_combined_default_prompt_fits_limit_for_all_options(style):
    for livestock in LIVESTOCK_OPTIONS:
        positive = build_prompt(
            200, 200, livestock, list(FEATURE_OPTIONS), style,
            "Kerbau" if livestock == "Lainnya" else "",
        )
        negative = NEGATIVE_PROMPT + (NEGATIVE_HYPERREALISM if style == "Render hiperrealistis" else "")
        assert len(compose_image_prompt(positive, negative)) <= MAX_PROMPT_CHARS


def test_hyperrealistic_style_prioritizes_layout_and_welfare():
    prompt = build_prompt(32, 8, "Sapi", ["Exhaust fan"], "Render hiperrealistis")
    assert "seperti foto arsitektur" in prompt
    assert "Prioritaskan dimensi, spesies, tata letak" in prompt
    assert "prinsip kesejahteraan hewan" in prompt
    assert "Exhaust fan" in prompt
    assert "Cooling pad" not in prompt
    assert "kartun" in NEGATIVE_HYPERREALISM


@pytest.mark.parametrize(
    ("style", "expected", "unexpected"),
    [
        ("Sketsa pensil arsitektural", "arsiran grafit", "fotorealistis"),
        ("Render realistis", "material bangunan wajar", "arsiran grafit"),
        ("Ilustrasi isometrik teknis", "proyeksi isometrik bersih", "seperti foto arsitektur"),
        ("Render hiperrealistis", "seperti foto arsitektur", "proyeksi isometrik bersih"),
    ],
)
def test_each_visual_style_has_distinct_instruction(style, expected, unexpected):
    prompt = build_prompt(32, 8, "Ayam broiler", ["Exhaust fan"], style)
    assert f"Gaya visual yang wajib dipatuhi: {style}" in prompt
    assert expected in prompt
    assert unexpected not in prompt


def test_combined_prompt_allows_empty_negative_and_rejects_oversized_result():
    assert compose_image_prompt("  Gambar sapi  ", "   ") == "Gambar sapi"
    assert compose_image_prompt(" Gambar sapi ", " Kabut ") == (
        "Gambar sapi\n\nHindari dalam gambar (negative prompt): Kabut"
    )
    with pytest.raises(ValueError, match="8000"):
        compose_image_prompt("a" * MAX_PROMPT_CHARS, "Kabut")
    with pytest.raises(ValueError, match="8000"):
        compose_image_prompt(" ", "Kabut")
    with pytest.raises(ValueError, match="Negative prompt"):
        compose_image_prompt("Gambar sapi", None)


def test_prompt_does_not_invent_unselected_ventilation_equipment():
    prompt = build_prompt(32, 8, "Bebek pedaging", [], "Render realistis")
    assert "cooling pad" not in prompt.lower()
    assert "exhaust fan" not in prompt.lower()
    assert "pintu" in prompt.lower()


def test_prompt_does_not_claim_elongated_for_near_square_plan():
    prompt = build_prompt(10, 8, "Ayam broiler", [], "Render realistis")
    assert "bentuk memanjang" not in prompt.lower()


def test_planning_brief_is_explicit_about_unknowns_and_next_steps():
    brief = build_planning_brief(32, 8, "Ayam broiler", ["Exhaust fan"])
    assert "luas 256 m²" in brief["decisions"][0]
    assert any("Kapasitas ternak" in item for item in brief["assumptions"])
    assert any("Survei lokasi" in item for item in brief["phases"])
    assert any("Cooling pad belum dipilih" in item for item in brief["risks"])


def test_get_api_key_prefers_streamlit_secrets_over_environment(monkeypatch):
    monkeypatch.setenv("TRUST_API_KEY", "env-key")
    monkeypatch.setattr("app.st.secrets", {"TRUST_API_KEY": "  secret-key  "})
    assert get_api_key() == "secret-key"


def test_get_api_key_falls_back_to_streamlit_secrets(monkeypatch):
    monkeypatch.delenv("TRUST_API_KEY", raising=False)
    monkeypatch.setattr("app.st.secrets", {"TRUST_API_KEY": "secret-key"})
    assert get_api_key() == "secret-key"


def test_get_api_key_falls_back_to_environment_if_secret_empty(monkeypatch):
    monkeypatch.setenv("TRUST_API_KEY", "  env-key  ")
    monkeypatch.setattr("app.st.secrets", {"TRUST_API_KEY": "   "})
    assert get_api_key() == "env-key"


def test_get_api_key_returns_none_when_missing_or_empty(monkeypatch):
    monkeypatch.delenv("TRUST_API_KEY", raising=False)
    monkeypatch.setattr("app.st.secrets", {})
    assert get_api_key() is None
    monkeypatch.setenv("TRUST_API_KEY", "   ")
    assert get_api_key() is None


def test_get_api_key_rejects_non_string_secret(monkeypatch):
    monkeypatch.delenv("TRUST_API_KEY", raising=False)
    monkeypatch.setattr("app.st.secrets", {"TRUST_API_KEY": 123})
    assert get_api_key() is None


def test_get_api_key_handles_unavailable_secrets(monkeypatch):
    class UnavailableSecrets:
        def get(self, *args, **kwargs):
            raise FileNotFoundError("secrets unavailable")

    monkeypatch.delenv("TRUST_API_KEY", raising=False)
    monkeypatch.setattr("app.st.secrets", UnavailableSecrets())
    assert get_api_key() is None
