"""Antarmuka Streamlit untuk generator konsep kandang close house."""

from __future__ import annotations

import hashlib
import html
import math
import os

import streamlit as st

from trust_client import TrustAPIError, TrustServiceError, generate_bynara_image, generate_image


LIVESTOCK_OPTIONS = (
    "Ayam broiler", "Ayam petelur", "Bebek pedaging", "Sapi", "Kambing", "Domba", "Lainnya",
)
LIVESTOCK_DETAILS = {
    "Ayam broiler": " Ayam broiler berada di lantai beralas sekam kering, tanpa kandang baterai.",
    "Ayam petelur": (
        " Ayam petelur ditampilkan dengan sistem lantai, alas litter dan sarang bertelur; "
        "jangan campur dengan kandang baterai."
    ),
    "Bebek pedaging": (
        " Bebek pedaging berada di lantai beralas litter kering, bukan di kolam air; "
        "sediakan akses air untuk membasahi kepala dan membersihkan mata serta lubang hidung "
        "tanpa membuat litter basah."
    ),
    "Sapi": " Sapi berada di area berlantai tidak licin dengan ruang gerak dan tempat istirahat.",
    "Kambing": " Kambing berada di area kering dengan tempat istirahat dan ruang gerak.",
    "Domba": " Domba berada di area kering dengan tempat istirahat dan ruang gerak.",
}
# ponytail: Prinsip umum tanpa angka kepadatan; penilaian kepatuhan butuh spesies, umur, iklim, dan aturan setempat.
WELFARE_DETAILS = {
    "Ayam broiler": " Sediakan litter kering, ruang bergerak dan beristirahat, serta akses pakan dan air merata.",
    "Ayam petelur": " Sediakan tenggeran, sarang bertelur, area mengais, dan mandi debu yang dapat diakses.",
    "Bebek pedaging": " Sediakan area bergerak dan beristirahat serta akses air untuk perilaku membersihkan diri.",
    "Sapi": " Sediakan ruang untuk berdiri, berbaring, dan bergerak alami; alas istirahat nyaman dan lantai tidak licin.",
    "Kambing": " Sediakan area kering untuk beristirahat, bergerak, dan berinteraksi sosial tanpa kepadatan berlebih.",
    "Domba": " Sediakan area kering untuk beristirahat, bergerak, dan berinteraksi sosial tanpa kepadatan berlebih.",
}
WELFARE_BASE = (
    " Terapkan prinsip kesejahteraan hewan: air minum bersih dan pakan yang mudah dijangkau "
    "semua ternak, ruang gerak dan istirahat yang sesuai spesies, lantai atau alas bersih "
    "dan kering, ventilasi serta suhu yang nyaman tanpa angin langsung atau penumpukan "
    "amonia, pencahayaan dan siklus gelap-terang yang sesuai, serta akses pemeriksaan "
    "dan penanganan ternak sakit. Tata ruang harus mendukung perilaku alami dan "
    "penanganan yang tenang untuk mengurangi takut serta stres. Sediakan jalur inspeksi "
    "dan area terpisah untuk ternak sakit tanpa mengurangi ruang ternak lain. "
    "Jangan menggambarkan ternak berdesakan atau terhalang dari pakan dan air."
)
MAX_PROMPT_CHARS = 8000
PAGE_STYLES = """
<style>
  .stApp { background: #f8f7f2; color: #1b3028; }
  .block-container { max-width: 1280px; padding-top: 2.4rem; padding-bottom: 4rem; }
  h1, h2, h3 { color: #173b30 !important; letter-spacing: -.035em; }
  h1 { font-weight: 750 !important; line-height: 1.12 !important; }
  .k-eyebrow { color: #a04f2c; font-size: .76rem; font-weight: 750; letter-spacing: .16em; text-transform: uppercase; margin-bottom: .65rem; }
  .k-steps { display: flex; flex-wrap: wrap; gap: .6rem; margin: 1.4rem 0 2rem; }
  .k-steps span { background: #e9eee5; color: #315548; border: 1px solid #d7e1d5; border-radius: 999px; padding: .4rem .8rem; font-size: .82rem; font-weight: 600; }
  .k-section { border-top: 2px solid #c7d4c6; padding-top: .8rem; margin-bottom: 1.1rem; color: #426053; font-size: .78rem; font-weight: 750; letter-spacing: .11em; text-transform: uppercase; }
  .k-section strong { color: #ad5836; margin-right: .6rem; }
  .k-summary { background: #193f33; color: #f5f4e8; border-radius: 16px; padding: 1.4rem 1.6rem; margin: .25rem 0 1rem; }
  .k-summary-label { color: #b8d4bd; font-size: .75rem; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; }
  .k-summary-value { font-size: clamp(2rem, 4vw, 3rem); font-weight: 750; letter-spacing: -.05em; line-height: 1.2; margin: .4rem 0; }
  .k-summary-foot { color: #d8e8d8; font-size: .87rem; }
  .k-diagram { border: 1px solid #d9dfd5; border-radius: 16px; background: #fffefa; padding: 1.25rem; margin: 0 0 1.3rem; }
  .k-diagram-head { display: flex; justify-content: space-between; gap: .8rem; align-items: baseline; margin-bottom: 1rem; color: #254638; font-size: .88rem; font-weight: 700; }
  .k-diagram-head small { color: #708277; font-weight: 500; text-align: right; }
  .k-plan { display: grid; grid-template-columns: 1fr 3fr 1fr; min-height: 106px; border: 2px solid #456555; border-radius: 7px; overflow: hidden; }
  .k-plan > div { display: flex; flex-direction: column; justify-content: center; align-items: center; gap: .25rem; text-align: center; padding: .6rem .3rem; font-size: .78rem; font-weight: 700; }
  .k-plan > div + div { border-left: 1px dashed #8da99a; }
  .k-inlet { background: #dce9db; color: #305444; }
  .k-house { background: repeating-linear-gradient(90deg, #f1f0e6 0, #f1f0e6 24px, #eae9df 24px, #eae9df 25px); color: #254638; }
  .k-outlet { background: #e9dacc; color: #75492e; }
  .k-plan small { font-weight: 500; font-size: .68rem; }
  .k-diagram-note { color: #65776a; font-size: .76rem; margin-top: .85rem; line-height: 1.5; }
  div.stButton > button[kind="primary"] { background: #b85c36; border-color: #b85c36; color: white; font-weight: 700; min-height: 3rem; }
  div.stButton > button[kind="primary"]:hover { background: #984726; border-color: #984726; color: white; }
  div.stButton > button:focus-visible, div.stDownloadButton > button:focus-visible { outline: 3px solid #b85c36; outline-offset: 3px; }
  @media (max-width: 640px) {
    .block-container { padding-top: 1.5rem; }
    .k-summary { padding: 1.1rem; }
    .k-diagram { padding: .9rem; }
    .k-plan { min-height: 88px; }
    .k-plan > div { font-size: .68rem; }
  }
</style>
"""
FEATURE_OPTIONS = (
    "Cooling pad",
    "Exhaust fan",
    "Jalur pakan otomatis",
    "Nipple drinker",
    "Tempat minum otomatis",
    "Zona biosekuriti",
)
STYLE_OPTIONS = (
    "Sketsa pensil arsitektural",
    "Render realistis",
    "Ilustrasi isometrik teknis",
    "Render hiperrealistis",
)
STYLE_INSTRUCTIONS = {
    "Sketsa pensil arsitektural": (
        " Gunakan gaya sketsa pensil arsitektural manual: garis kontur dan garis konstruksi yang terlihat, "
        "arsiran grafit secukupnya, palet monokrom hangat, anotasi visual minimal, dan kesan studi konsep; "
        "jangan membuatnya tampak seperti foto atau ilustrasi kartun."
    ),
    "Render realistis": (
        " Gunakan render arsitektur realistis atau fotorealistis untuk presentasi awal: material bangunan wajar, "
        "cahaya siang alami, perspektif terkendali, warna netral, dan proporsi konstruksi yang masuk akal."
    ),
    "Ilustrasi isometrik teknis": (
        " Gunakan ilustrasi isometrik teknis: proyeksi isometrik bersih, garis tegas, warna kode yang terkendali, "
        "struktur dan alur peralatan mudah dibaca, tampilan informatif seperti lembar konsep teknik; "
        "hindari efek kamera dramatis dan fotorealisme."
    ),
    "Render hiperrealistis": (
        " Gunakan render hiperrealistis seperti foto arsitektur beresolusi tinggi: tekstur material dan bulu ternak alami, "
        "bayangan serta refleksi fisik masuk akal, pencahayaan siang lembut, fokus tajam pada struktur dan peralatan, "
        "warna netral, dan detail konstruksi nyata. Prioritaskan dimensi, spesies, tata letak, peralatan terpilih, "
        "dan kesejahteraan hewan di atas efek estetika."
    ),
}
NEGATIVE_PROMPT = (
    "Anatomi ternak keliru, kaki atau kepala tambahan, hewan menyatu dengan "
    "peralatan, ternak berdesakan, lantai kotor atau basah, pakan dan air tidak terjangkau, "
    "struktur melayang, proporsi bangunan tidak sesuai dimensi, perspektif terdistorsi, "
    "peralatan otomatis tambahan yang tidak dipilih, aliran ventilasi terhalang, detail kabur, artefak gambar, "
    "watermark, teks dan label palsu."
)
NEGATIVE_HYPERREALISM = (
    " Tampilan kartun, sketsa, ilustrasi datar, tekstur plastik, pencahayaan "
    "berlebihan, saturasi tidak alami, dan efek fantasi."
)


def validate_dimensions(length_m: float, width_m: float) -> None:
    """Validasi setiap sisi kandang dalam rentang aman 1–200 meter."""
    if isinstance(length_m, bool) or isinstance(width_m, bool):
        raise ValueError("Dimensi harus berupa angka yang valid.")
    try:
        finite = all(math.isfinite(value) for value in (length_m, width_m))
    except (TypeError, ValueError) as exc:
        raise ValueError("Dimensi harus berupa angka yang valid.") from exc
    if not finite:
        raise ValueError("Dimensi harus berupa angka yang valid.")
    if not all(1 <= value <= 200 for value in (length_m, width_m)):
        raise ValueError("Panjang dan lebar harus antara 1 hingga 200 meter.")


def calculate_area(length_m: float, width_m: float) -> float:
    """Hitung luas kandang dalam meter persegi."""
    validate_dimensions(length_m, width_m)
    return round(length_m * width_m, 2)


def _format_number(value: float) -> str:
    return f"{value:g}"


def build_prompt(
    length_m: float,
    width_m: float,
    livestock: str,
    features: list[str],
    style: str,
    custom_livestock: str = "",
) -> str:
    """Bangun prompt gambar dari pilihan UI dan nama ternak lain yang valid."""
    if not isinstance(features, list) or any(not isinstance(feature, str) for feature in features):
        raise ValueError("fitur kandang harus berupa daftar pilihan yang valid.")
    validate_dimensions(length_m, width_m)
    if livestock not in LIVESTOCK_OPTIONS:
        raise ValueError("Jenis ternak tidak tersedia.")
    if livestock == "Lainnya":
        if not isinstance(custom_livestock, str):
            raise ValueError("Isi jenis ternak lain (maksimum 60 karakter tanpa baris baru).")
        custom_livestock = custom_livestock.strip()
        if not custom_livestock or len(custom_livestock) > 60 or not custom_livestock.isprintable():
            raise ValueError("Isi jenis ternak lain (maksimum 60 karakter tanpa baris baru).")
        livestock_name = custom_livestock
    else:
        livestock_name = livestock
    if style not in STYLE_OPTIONS:
        raise ValueError("Gaya visual tidak tersedia.")
    if any(feature not in FEATURE_OPTIONS for feature in features):
        raise ValueError("Ada fitur kandang yang tidak tersedia.")

    area = calculate_area(length_m, width_m)
    ratio = max(length_m, width_m) / min(length_m, width_m)
    feature_text = ", ".join(features) if features else "tanpa peralatan tambahan"
    shape_instruction = ""
    if ratio >= 2:
        shape_instruction = (
            " Denah harus tampak berbentuk memanjang sesuai proporsi; "
            "jangan menggambarkannya sebagai bangunan persegi."
        )

    ventilation = ""
    if "Cooling pad" in features:
        ventilation += (
            " Cooling pad adalah deret panel selulosa sarang lebah basah dalam bingkai "
            "pada dinding ujung pendek sisi masuk udara; tampakkan permukaan panel "
            "di sisi luar dan talang air di bawahnya, bukan pintu, kipas, atau panel "
            "yang berdiri sendiri di tengah kandang. Jika ada tanda atau panah "
            "bertuliskan 'Cooling pad', ujung panah harus tepat menyentuh panel "
            "sarang lebah pada sisi inlet tersebut, bukan kipas, pintu, atap, atau "
            "peralatan di dalam kandang; jika tidak bisa ditunjuk tepat, hilangkan "
            "tanda dan panah tetapi tetap tampilkan panelnya."
        )
    if "Exhaust fan" in features:
        ventilation += (
            " Exhaust fan berupa kipas aksial berbingkai dengan bilah dan kisi pelindung "
            "yang terpasang menembus dinding ujung pendek sisi buang, bukan pintu, "
            "jendela, atau kipas berdiri bebas di dalam kandang."
        )
    if "Cooling pad" in features and "Exhaust fan" in features:
        ventilation += (
            " Tempatkan pad dan kipas di ujung berlawanan agar aliran udara "
            "memanjang melalui kandang, tanpa pintu menembus keduanya."
        )
    equipment = ""
    poultry = livestock in {"Ayam broiler", "Ayam petelur", "Bebek pedaging"}
    if "Jalur pakan otomatis" in features:
        equipment += (
            " Jalur pakan otomatis berupa pipa dan deret pan feeder sejajar sumbu "
            "panjang di atas lantai area ternak, tersambung ke silo di luar kandang."
            if poultry else
            " Jalur pakan otomatis menuju palung pakan yang sesuai ukuran ternak, "
            "berada di sepanjang area ternak dan terpisah dari jalur minum."
        )
    if "Nipple drinker" in features:
        equipment += (
            " Nipple drinker berupa deret pipa air dengan nipple yang digantung "
            "sejajar sumbu panjang kandang, pada ketinggian terjangkau ternak; "
            "bukan keran dinding."
            if poultry else
            " Nipple drinker berupa deret nipple yang sesuai ukuran ternak dan "
            "dipasang pada ketinggian terjangkau ternak, bukan keran dinding."
        )
    if "Tempat minum otomatis" in features:
        equipment += (
            " Tempat minum otomatis berupa bak atau palung minum sesuai ukuran ternak "
            "di area ternak, terpisah dari jalur pakan."
        )
    if "Jalur pakan otomatis" in features and "Nipple drinker" in features:
        equipment += " Pisahkan jalur pakan dan jalur minum agar keduanya terlihat utuh."
    livestock_detail = LIVESTOCK_DETAILS.get(livestock, "")
    biosecurity = (
        " Zona biosekuriti adalah ruang masuk kecil tertutup yang menempel di LUAR "
        "dinding samping kandang, di depan pintu akses pekerja, dengan pintu luar "
        "dan pintu dalam terpisah serta tempat ganti alas kaki dan cuci tangan. "
        "Jangan letakkan zona biosekuriti, pos keamanan, atau ruang ganti di dalam "
        "area ternak; jangan tampilkan petugas keamanan atau pagar di dalam kandang."
        if "Zona biosekuriti" in features else ""
    )
    style_instruction = STYLE_INSTRUCTIONS[style]
    composition_instruction = (
        " Gunakan satu sudut pandang isometrik potongan atap: sebagian atap diangkat hanya secara visual, "
        "tiga sisi bangunan tetap terbaca, seluruh panjang lantai dan setiap fitur yang dipilih tampak tanpa "
        "tertutup atap atau dinding."
        if style == "Ilustrasi isometrik teknis" else
        " Tampilkan bangunan dari sudut pandang arsitektur yang paling membantu membaca bentuk dan tata letak; "
        "potongan atap hanya digunakan sebagai inset atau bukaan visual kecil bila diperlukan, bukan sebagai "
        "gaya utama gambar."
    )

    return (
        f"Buat gambar konsep kandang close house untuk {livestock_name}. "
        f"Dimensi pasti: panjang {_format_number(length_m)} meter dan lebar "
        f"{_format_number(width_m)} meter, luas {area:g} meter persegi."
        f"{shape_instruction} Fitur yang terlihat: {feature_text}. "
        "Rancang sebagai kandang tertutup yang dapat dibangun: atap miring, dinding, "
        "lantai, akses servis dan peralatan berskala konsisten; deret peralatan "
        "berulang mengikuti panjang bangunan, bukan satu perangkat raksasa. "
        "Potongan atap hanya alat visualisasi, bukan lubang pada kandang jadi; "
        "dinding dan ventilasi tetap rapat sesuai fungsi kandang tertutup. "
        "Pintu akses pekerja di sisi samping, bukan tepat di area inlet atau outlet ventilasi. "
        "Jangan tambahkan pintu dekoratif, pintu di balik perangkat ventilasi, atau bukaan "
        "yang memutus aliran udara. Perlihatkan hanya peralatan otomatis yang dipilih; "
        "sarana dasar pakan dan air serta fasilitas kesejahteraan tetap harus tampak. "
        f"{composition_instruction} "
        "Pastikan setiap fitur yang dipilih tampak dan dapat dibaca tanpa mengubah lokasi fisiknya. "
        "Pertahankan dinding sebagai batas fisik yang jelas: peralatan ternak di dalam, "
        "perangkat eksterior di luar; jangan pindahkan fitur ke tengah kandang demi "
        "memperlihatkannya. Jangan tambahkan bangunan, orang, atau perangkat "
        "yang tidak diperlukan."
        f"{ventilation}{equipment}{biosecurity}{livestock_detail}"
        f"{WELFARE_BASE}{WELFARE_DETAILS.get(livestock, ' Sesuaikan fasilitas dengan kebutuhan spesies yang disebutkan.')}"
        f" Gaya visual yang wajib dipatuhi: {style}.{style_instruction} "
        "Tampilkan struktur, ventilasi, dan tata letak secara jelas. " 
        "Hindari teks kecil atau label yang sulit dibaca; dimensi "
        "pada gambar hanyalah ilustrasi dan perlu diverifikasi."
    )


def validate_prompt(prompt: str) -> str:
    if not isinstance(prompt, str):
        raise ValueError("Prompt harus berupa teks.")
    prompt = prompt.strip()
    if not prompt or len(prompt) > MAX_PROMPT_CHARS:
        raise ValueError(f"Prompt harus diisi dan tidak lebih dari {MAX_PROMPT_CHARS} karakter.")
    return prompt

def compose_image_prompt(prompt: str, negative_prompt: str) -> str:
    if not isinstance(negative_prompt, str):
        raise ValueError("Negative prompt harus berupa teks.")
    prompt = validate_prompt(prompt)
    negative_prompt = negative_prompt.strip()
    if not negative_prompt:
        return prompt
    return validate_prompt(f"{prompt}\n\nHindari dalam gambar (negative prompt): {negative_prompt}")


def build_planning_brief(
    length_m: float,
    width_m: float,
    livestock: str,
    features: list[str],
    custom_livestock: str = "",
) -> dict[str, list[str] | str]:
    """Susun brief perencanaan awal tanpa mengarang data engineering yang belum ada."""
    validate_dimensions(length_m, width_m)
    area = calculate_area(length_m, width_m)
    ratio = max(length_m, width_m) / min(length_m, width_m)
    livestock_name = custom_livestock.strip() if livestock == "Lainnya" else livestock
    if livestock_name not in LIVESTOCK_OPTIONS and livestock != "Lainnya":
        raise ValueError("Jenis ternak tidak tersedia.")
    if livestock == "Lainnya" and (not livestock_name or len(livestock_name) > 60):
        raise ValueError("Isi jenis ternak lain (maksimum 60 karakter tanpa baris baru).")
    if any(feature not in FEATURE_OPTIONS for feature in features):
        raise ValueError("Ada fitur kandang yang tidak tersedia.")

    decisions = [
        f"Bangunan {length_m:g} × {width_m:g} m dengan luas {area:g} m² dan rasio sisi {ratio:.2f}:1.",
        f"Sistem pemeliharaan direncanakan untuk {livestock_name} dengan fitur: "
        f"{', '.join(features) if features else 'belum ada fitur otomatis yang dipilih'}.",
        "Akses pekerja, jalur pakan, jalur air, dan area ternak perlu dipisahkan agar inspeksi dan sanitasi tidak saling mengganggu.",
    ]
    assumptions = [
        "Kapasitas ternak, umur atau fase produksi, lokasi, iklim, orientasi matahari, dan sumber utilitas belum ditentukan.",
        "Kebutuhan struktur, debit air, daya listrik, ukuran kipas, dan luas bukaan harus dihitung ulang oleh tenaga kompeten.",
        "Standar kesejahteraan, biosekuriti, drainase, dan perizinan mengikuti aturan yang berlaku di lokasi proyek.",
    ]
    phases = [
        "1. Validasi kebutuhan: tetapkan kapasitas, fase produksi, target operasi, anggaran, dan batas lahan.",
        "2. Survei lokasi: cek elevasi, drainase, arah angin dan matahari, akses kendaraan, listrik, air, serta jarak dari sumber risiko.",
        "3. Konsep tata ruang: kunci alur orang, ternak, pakan, limbah, udara masuk, udara keluar, dan area isolasi.",
        "4. Verifikasi teknis: minta perhitungan struktur, ventilasi, listrik, air, sanitasi, dan keselamatan sebelum konstruksi.",
        "5. Commissioning: uji aliran udara, suhu, kelembapan, kualitas air, alarm, kebersihan, dan prosedur operasional sebelum ternak masuk.",
    ]
    risks = []
    if ratio < 2:
        risks.append("Rasio bangunan relatif kompak; aliran udara dan pemisahan zona perlu diuji agar tidak ada area mati.")
    if "Cooling pad" not in features and livestock_name in {"Ayam broiler", "Ayam petelur", "Bebek pedaging"}:
        risks.append("Cooling pad belum dipilih; konfirmasi strategi pendinginan untuk kondisi panas dan kelembapan setempat.")
    if "Exhaust fan" not in features:
        risks.append("Exhaust fan belum dipilih; ventilasi mekanis dan pembuangan amonia harus ditentukan sebelum desain dikunci.")
    if "Zona biosekuriti" not in features:
        risks.append("Zona biosekuriti belum dipilih; tentukan titik cuci tangan, ganti alas kaki, dan batas akses pekerja.")
    risks.append("Kapasitas belum dihitung; jangan menempatkan ternak berdasarkan luas saja tanpa memperhitungkan spesies, umur, dan sistem pemeliharaan.")
    return {
        "title": f"Rencana awal kandang {livestock_name}",
        "decisions": decisions,
        "assumptions": assumptions,
        "phases": phases,
        "risks": risks,
    }

def get_api_key() -> str | None:
    """Utamakan Streamlit Secrets (lokal/Cloud), lalu environment variable lokal."""
    try:
        configured_key = st.secrets.get("TRUST_API_KEY", "")
    except (FileNotFoundError, KeyError):
        configured_key = ""
    if isinstance(configured_key, str) and configured_key.strip():
        return configured_key.strip()
    env_key = os.getenv("TRUST_API_KEY", "")
    return (env_key.strip() or None) if isinstance(env_key, str) else None


def get_nara_api_key() -> str | None:
    """Ambil kredensial Bynara dari secrets tanpa menampilkannya."""
    try:
        configured = st.secrets.get("NARA_API_KEY", "")
    except (FileNotFoundError, KeyError):
        configured = ""
    return (configured.strip() or None) if isinstance(configured, str) else None


def main() -> None:
    st.set_page_config(page_title="Konsep Kandang Close House", page_icon="🐔", layout="wide")
    st.markdown(PAGE_STYLES, unsafe_allow_html=True)
    st.markdown('<div class="k-eyebrow">STUDIO KANDANG / PERENCANAAN AWAL</div>', unsafe_allow_html=True)
    st.title("Generator Konsep Kandang Close House")
    st.caption("Rancang ukuran, pilih kebutuhan ternak, lalu buat visual konsep untuk diskusi awal.")
    st.markdown(
        '<div class="k-steps"><span>01 &nbsp; Atur kebutuhan</span>'
        '<span>02 &nbsp; Tinjau rencana</span><span>03 &nbsp; Buat visual</span></div>',
        unsafe_allow_html=True,
    )

    form_col, preview_col = st.columns([1, 1.05], gap="large")
    with form_col:
        st.markdown('<div class="k-section"><strong>01</strong> Ukuran bangunan</div>', unsafe_allow_html=True)
        st.caption("Masukkan dimensi awal dalam meter. Luas dihitung otomatis di sebelah kanan.")
        left, right = st.columns(2)
        with left:
            length_m = st.number_input("Panjang (meter)", 1.0, 200.0, 32.0, 0.5)
        with right:
            width_m = st.number_input("Lebar (meter)", 1.0, 200.0, 8.0, 0.5)

        st.markdown('<div class="k-section"><strong>02</strong> Kebutuhan ternak</div>', unsafe_allow_html=True)
        livestock = st.selectbox("Jenis ternak", LIVESTOCK_OPTIONS)
        custom_livestock = st.text_input("Jenis ternak lain") if livestock == "Lainnya" else ""
        poultry = livestock in {"Ayam broiler", "Ayam petelur", "Bebek pedaging"}
        features = st.multiselect(
            "Fitur kandang",
            FEATURE_OPTIONS,
            default=["Cooling pad", "Exhaust fan", "Jalur pakan otomatis", "Nipple drinker"]
            if poultry else ["Exhaust fan", "Tempat minum otomatis"],
            key=f"features_{'poultry' if poultry else 'other'}",
            help="Fitur awal menyesuaikan jenis ternak. Anda dapat menambah atau menghapusnya.",
        )
        st.markdown('<div class="k-section"><strong>03</strong> Gaya visual</div>', unsafe_allow_html=True)
        style = st.selectbox("Gaya visual", STYLE_OPTIONS)

        try:
            generated_prompt = build_prompt(
                length_m, width_m, livestock, list(features), style, custom_livestock
            )
        except ValueError as exc:
            generated_prompt = ""
            st.error(str(exc))
        source = (length_m, width_m, livestock, custom_livestock, tuple(features), style)
        source_id = hashlib.sha256(repr(source).encode()).hexdigest()
        if st.session_state.get("prompt_source") != source_id:
            st.session_state["prompt_text"] = generated_prompt
            st.session_state["negative_prompt_text"] = (
                NEGATIVE_PROMPT + NEGATIVE_HYPERREALISM
                if style == "Render hiperrealistis" else NEGATIVE_PROMPT
            )
            st.session_state["prompt_source"] = source_id
        with st.expander("Pengaturan lanjutan · sunting prompt"):
            st.caption("Opsional. Mengubah ukuran atau pilihan di atas akan menyusun ulang suntingan prompt.")
            prompt = st.text_area(
                "Prompt gambar (dapat diubah sebelum dikirim)", key="prompt_text", height=220,
                help="Mengubah pilihan di atas akan menyusun ulang prompt dan mengganti suntingan sebelumnya.",
            )
            negative_prompt = st.text_area(
                "Negative prompt (hal yang dihindari; dapat diubah)",
                key="negative_prompt_text", height=120,
                help="Dikirim sebagai bagian dari prompt gambar karena parameter negative_prompt terpisah tidak tersedia dalam kontrak API aplikasi.",
            )

    with preview_col:
        st.markdown('<div class="k-section"><strong>04</strong> Tinjau konsep awal</div>', unsafe_allow_html=True)
        area = calculate_area(length_m, width_m)
        aspect_ratio = max(length_m, width_m) / min(length_m, width_m)
        st.markdown(
            f'<div class="k-summary"><div class="k-summary-label">LUAS RENCANA</div>'
            f'<div class="k-summary-value">{area:g} m²</div>'
            f'<div class="k-summary-foot">{length_m:g} m panjang &nbsp;×&nbsp; {width_m:g} m lebar'
            f' &nbsp;·&nbsp; Rasio {aspect_ratio:.2f}:1</div></div>',
            unsafe_allow_html=True,
        )
        st.info(f"Luas: **{area:g} m²** · Rasio sisi: **{aspect_ratio:.2f}:1**")
        inlet = "Cooling pad" if "Cooling pad" in features else "Udara masuk*"
        outlet = "Exhaust fan" if "Exhaust fan" in features else "Udara keluar*"
        livestock_label = html.escape(custom_livestock.strip() or livestock)
        st.markdown(
            f'<div class="k-diagram"><div class="k-diagram-head">Skema alur bangunan'
            f'<small>Ilustrasi, bukan gambar teknis</small></div>'
            f'<div class="k-plan"><div class="k-inlet">{inlet}<small>INLET</small></div>'
            f'<div class="k-house">AREA TERNAK<small>{livestock_label}</small></div>'
            f'<div class="k-outlet">{outlet}<small>OUTLET</small></div></div>'
            f'<div class="k-diagram-note">* Posisi dan kebutuhan ventilasi harus diverifikasi.'
            f' Skema ini tidak menunjukkan ukuran atau penempatan peralatan yang pasti.</div></div>',
            unsafe_allow_html=True,
        )
        try:
            planning_brief = build_planning_brief(
                length_m, width_m, livestock, list(features), custom_livestock
            )
        except ValueError:
            planning_brief = None
        if planning_brief:
            st.subheader("Rencana awal yang realistis")
            st.caption("Keputusan awal, langkah kerja, dan hal yang masih perlu divalidasi.")
            with st.expander("Lihat brief perencanaan"):
                st.markdown(f"**Tujuan:** {planning_brief['title']} sebagai konsep awal yang siap divalidasi.")
                st.markdown("**Keputusan saat ini**")
                for item in planning_brief["decisions"]:
                    st.markdown(f"- {item}")
                st.markdown("**Urutan kerja yang disarankan**")
                for item in planning_brief["phases"]:
                    st.markdown(f"- {item}")
                st.markdown("**Asumsi yang masih harus dikonfirmasi**")
                for item in planning_brief["assumptions"]:
                    st.markdown(f"- {item}")
                st.markdown("**Risiko dan tindakan sebelum desain dikunci**")
                for item in planning_brief["risks"]:
                    st.markdown(f"- {item}")
        st.markdown('<div class="k-section"><strong>05</strong> Buat visual</div>', unsafe_allow_html=True)
        st.caption("Gambar dibuat dari pilihan saat ini dan prompt yang dapat disunting di panel kiri.")
        image_provider = st.radio(
            "Penyedia gambar", ("Trust", "Bynara"), horizontal=True,
            help="Trust dapat mencoba Bynara saat gangguan server/koneksi. Pilih Bynara untuk "
            "mengirim langsung tanpa mencoba Trust. Setiap permintaan dapat dikenai biaya.",
        )
        generate_clicked = st.button("Buat gambar konsep", type="primary", use_container_width=True)

    st.warning(
        "Hasil adalah rencana awal dan konsep visual, bukan gambar kerja konstruksi atau rekomendasi "
        "teknis. Gambar tidak membuktikan kepatuhan kesejahteraan hewan; kapasitas, "
        "kualitas udara, suhu, akses pakan dan air, serta kesehatan ternak perlu "
        "dinilai di lapangan menurut standar yang berlaku. Teks dan dimensi "
        "yang dirender model harus diverifikasi."
    )
    st.caption("Developed by [Galuh Adi Insani](https://adioranye.my.id/)")

    if not generate_clicked:
        return

    if not generated_prompt:
        return
    positive_prompt = prompt.strip()
    try:
        prompt = compose_image_prompt(prompt, negative_prompt)
    except ValueError as exc:
        st.error(str(exc))
        return

    st.subheader("Prompt yang digunakan")
    st.code(prompt, language=None)
    api_key = get_api_key() if image_provider == "Trust" else get_nara_api_key()
    if not api_key and image_provider == "Trust":
        st.error(
            "TRUST_API_KEY belum dikonfigurasi. Di Streamlit Community Cloud, buka "
            "App settings → Secrets, simpan TRUST_API_KEY, ENDPOINT, dan MODEL sebagai "
            "TOML tingkat teratas (tanpa [section]), lalu jalankan ulang aplikasi. "
            "Untuk pengembangan lokal, gunakan .streamlit/secrets.toml atau environment variable."
        )
        return
    if not api_key:
        st.error(
            "NARA_API_KEY belum dikonfigurasi. Tambahkan ke App settings → Secrets "
            "(Cloud) atau .streamlit/secrets.toml (lokal)."
        )
        return

    try:
        with st.spinner("Membuat gambar konsep…"):
            if image_provider == "Bynara":
                image_bytes = generate_bynara_image(
                    positive_prompt, negative_prompt.strip(), api_key,
                )
                provider = "Bynara"
            else:
                try:
                    image_bytes = generate_image(prompt, api_key)
                    provider = "Trust"
                except TrustServiceError as trust_error:
                    st.warning(f"Permintaan Trust gagal: {trust_error}")
                    nara_key = get_nara_api_key()
                    if not nara_key:
                        raise TrustAPIError(
                            "Trust sedang bermasalah dan fallback Bynara belum tersedia: "
                            "isi NARA_API_KEY di App settings → Secrets (Cloud) atau "
                            ".streamlit/secrets.toml (lokal)."
                        ) from None
                    st.info("Trust tidak tersedia. Mencoba Bynara sebagai penyedia cadangan…")
                    image_bytes = generate_bynara_image(
                        positive_prompt, negative_prompt.strip(), nara_key,
                    )
                    provider = "Bynara"
    except TrustAPIError as exc:
        st.error(str(exc))
        return

    st.image(image_bytes, caption=f"Hasil konsep kandang · {provider}", use_container_width=True)
    st.download_button(
        "Unduh PNG",
        data=image_bytes,
        file_name="konsep-kandang-close-house.png",
        mime="image/png",
    )
    st.success(f"Gambar konsep berhasil dibuat melalui {provider}.")


if __name__ == "__main__":
    main()
