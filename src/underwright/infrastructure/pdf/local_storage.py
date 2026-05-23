from __future__ import annotations

import os
from pathlib import Path, PurePath


class LocalPdfArtifactStorage:
    """Filesystem-backed PDF artifact storage."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)

    @classmethod
    def from_environment(cls) -> "LocalPdfArtifactStorage":
        return cls(os.getenv("UNDERWRIGHT_PDF_STORAGE_DIR", "generated/pdfs"))

    def write(self, filename: str, content: bytes) -> str:
        safe_name = self._safe_filename(filename)
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / safe_name
        path.write_bytes(content)
        return safe_name

    def exists(self, storage_key: str) -> bool:
        return self.path_for(storage_key).is_file()

    def read(self, storage_key: str) -> bytes:
        return self.path_for(storage_key).read_bytes()

    def path_for(self, storage_key: str) -> Path:
        return self.root / self._safe_filename(storage_key)

    def _safe_filename(self, filename: str) -> str:
        name = PurePath(filename).name.strip()
        if not name:
            raise ValueError("PDF filename is required")
        return name


__all__ = ["LocalPdfArtifactStorage"]
