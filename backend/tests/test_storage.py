from __future__ import annotations

import zipfile
from pathlib import Path

from app.storage import Storage


def test_safe_filename_strips_paths() -> None:
    storage = Storage(Path("/tmp/ins-test"))
    assert storage.safe_filename("../../etc/passwd") == "passwd"
    assert storage.safe_filename("a/b/c.jpg") == "c.jpg"
    assert storage.safe_filename("") == "file"
    assert storage.safe_filename("..") == "file"


def test_unique_path(tmp_path: Path) -> None:
    storage = Storage(tmp_path)
    first = tmp_path / "photo.jpg"
    first.write_text("one")
    second = storage.unique_path(first)
    assert second == tmp_path / "photo_2.jpg"
    second.write_text("two")
    assert storage.unique_path(first) == tmp_path / "photo_3.jpg"


def test_build_archive(tmp_path: Path) -> None:
    storage = Storage(tmp_path)
    storage.ensure_root()
    job_dir = storage.job_dir("job-1")
    job_dir.mkdir()
    first = job_dir / "first.jpg"
    second = job_dir / "second.mp4"
    first.write_bytes(b"jpeg")
    second.write_bytes(b"mp4")

    archive = storage.build_archive(
        "job-1",
        [(0, "first.jpg", first), (1, "second.mp4", second)],
    )

    assert archive.is_file()
    with zipfile.ZipFile(archive) as bundle:
        assert bundle.namelist() == ["01_first.jpg", "02_second.mp4"]
        assert bundle.read("01_first.jpg") == b"jpeg"
