import pytest


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("PARSE_VIDEO_DATA_DIR", str(tmp_path))
