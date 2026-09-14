"""Private storage for evidentiary snapshot artifacts.

`EvidenceSnapshot` (see `news/evidence_snapshot.py`) only ever stores a
*reference* to an artifact — `storage_key` — never the bytes themselves and
never a secret. Implementations of `SnapshotStorage` are where the actual
content (HTML capture, screenshot, PDF, …) lives, kept out of the database
and out of any publicly served path.

`LocalFileSnapshotStorage` is the local development/test backend used by
`get_snapshot_storage()` today. It writes under `media/evidence_snapshots/`,
which is already excluded from git and is not a static/public directory.
Swap `get_snapshot_storage()` for a real private backend (e.g. a
non-public object storage bucket) before relying on this beyond local use;
see docs/EVIDENCE_SNAPSHOT.md.
"""
from __future__ import annotations

import abc
import os
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings


class SnapshotStorageError(Exception):
    """Raised when a snapshot artifact cannot be stored or retrieved."""


@dataclass(frozen=True)
class StoredArtifact:
    key: str
    size: int


class SnapshotStorage(abc.ABC):
    """Private storage for evidentiary artifacts.

    Implementations must not expose a public URL for stored content and must
    not silently overwrite an existing key with different bytes — callers
    derive `key` from a content hash, so a mismatch signals a bug upstream.
    """

    @abc.abstractmethod
    def put(self, key: str, content: bytes) -> StoredArtifact:
        ...

    @abc.abstractmethod
    def get(self, key: str) -> bytes:
        ...

    @abc.abstractmethod
    def exists(self, key: str) -> bool:
        ...

    @abc.abstractmethod
    def delete(self, key: str) -> None:
        ...


class LocalFileSnapshotStorage(SnapshotStorage):
    """Filesystem-backed storage for local development and tests only.

    Never point `root` at a path served publicly (e.g. `STATIC_ROOT`).
    """

    def __init__(self, root: str | os.PathLike):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        if not key or not key.strip():
            raise SnapshotStorageError("Empty snapshot storage key.")
        candidate = (self.root / key).resolve()
        if candidate != self.root and self.root not in candidate.parents:
            raise SnapshotStorageError(f"Snapshot storage key escapes the storage root: {key!r}.")
        return candidate

    def put(self, key: str, content: bytes) -> StoredArtifact:
        path = self._path(key)
        if path.is_file() and path.read_bytes() != content:
            raise SnapshotStorageError(
                f"Refusing to overwrite existing snapshot artifact with different content: {key!r}.")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return StoredArtifact(key=key, size=len(content))

    def get(self, key: str) -> bytes:
        path = self._path(key)
        if not path.is_file():
            raise SnapshotStorageError(f"No snapshot artifact stored for key {key!r}.")
        return path.read_bytes()

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def delete(self, key: str) -> None:
        path = self._path(key)
        if path.is_file():
            path.unlink()


def get_snapshot_storage() -> SnapshotStorage:
    """Return the configured snapshot storage backend.

    Defaults to a local, git-ignored directory suitable for development and
    tests. Override via `settings.EVIDENCE_SNAPSHOT_STORAGE_ROOT` or replace
    this factory entirely once a private production backend is chosen.
    """
    root = getattr(settings, "EVIDENCE_SNAPSHOT_STORAGE_ROOT", None) or (
        Path(settings.BASE_DIR) / "media" / "evidence_snapshots")
    return LocalFileSnapshotStorage(root)
