import zipfile

from build_zip import FILES, build_zip


def test_zip_contains_only_allowlisted_project_files(tmp_path):
    archive_path = build_zip(tmp_path / "project.zip")
    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
        contents = b"\n".join(archive.read(name) for name in names)

    assert set(names) == {f"streamlit-kandang/{path}" for path in FILES}
    assert "streamlit-kandang/.env" not in names
    assert "streamlit-kandang/.streamlit/secrets.toml" not in names
    assert all(".venv" not in name and "__pycache__" not in name for name in names)
    assert b"TRUST_API_KEY=\n" in contents
    secret_marker = b"Bearer " + b"REAL" + b"-PRODUCTION-KEY"
    assert secret_marker not in contents
