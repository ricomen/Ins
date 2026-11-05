from __future__ import annotations

import re
import shutil
import zipfile
from pathlib import Path

_SAFE_NAME_RE = re.compile(r"[^\w.\- ()]+", re.UNICODE)


class Storage:
    """Local disk storage for job files and generated archives."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.archives = root / "_archives"

    def ensure_root(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.archives.mkdir(parents=True, exist_ok=True)

    def job_dir(self, job_id: str) -> Path:
        return self.root / job_id

    def safe_filename(self, filename: str) -> str:
        name = Path(filename.replace("\x00", "")).name.strip()
        name = _SAFE_NAME_RE.sub("_", name)
        if not name or name in {".", ".."}:
            name = "file"
        return name[:180]

    def unique_path(self, path: Path) -> Path:
        if not path.exists():
            return path
        counter = 2
        while True:
            candidate = path.with_name(f"{path.stem}_{counter}{path.suffix}")
            if not candidate.exists():
                return candidate
            counter += 1

    def archive_path(self, job_id: str) -> Path:
        return self.archives / f"{job_id}.zip"

    def delete_job(self, job_id: str) -> None:
        shutil.rmtree(self.job_dir(job_id), ignore_errors=True)
        self.delete_archive(job_id)

    def delete_archive(self, job_id: str) -> None:
        self.archive_path(job_id).unlink(missing_ok=True)

    def build_archive(
        self, job_id: str, files: list[tuple[int, str, Path]]
    ) -> Path:
        self.archives.mkdir(parents=True, exist_ok=True)
        archive = self.archive_path(job_id)
        temporary = archive.with_suffix(".zip.part")
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as bundle:
            for position, filename, path in files:
                if not path.is_file():
                    continue
                bundle.write(path, arcname=f"{position + 1:02d}_{filename}")
        temporary.replace(archive)
        return archive
