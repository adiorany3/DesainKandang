"""Buat arsip distribusi dari berkas proyek yang diizinkan."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

FILES = (
    "app.py",
    "trust_client.py",
    "build_zip.py",
    "requirements.txt",
    "README.md",
    ".env.example",
    ".streamlit/config.toml",
    "tests/test_app_helpers.py",
    "tests/test_package.py",
    "tests/test_streamlit_ui.py",
    "tests/test_trust_client.py",
)


def build_zip(destination: str | Path) -> Path:
    destination = Path(destination)
    root = Path(__file__).resolve().parent
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.tmp")
    try:
        with ZipFile(temporary, "w", compression=ZIP_DEFLATED) as archive:
            for name in FILES:
                archive.write(root / name, f"streamlit-kandang/{name}")
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


if __name__ == "__main__":
    output = Path(__file__).resolve().parent / "dist" / "streamlit-kandang.zip"
    output.parent.mkdir(exist_ok=True)
    build_zip(output)
