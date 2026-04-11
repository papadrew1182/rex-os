"""Attachment storage abstraction.

Sprint F: formalized as a pluggable adapter boundary. All storage access
flows through ``StorageAdapter``. Concrete adapters are selected at
process startup via env and registered here — no cloud/network code lives
in the call sites.

Environment contract
--------------------
``REX_STORAGE_BACKEND`` (default: ``local``)
    Selects the adapter. Supported values:
    - ``local`` — filesystem-backed, production-safe for single-host dev.
    - ``memory`` — in-process dict; testing only.
    - ``s3``    — S3/R2-compatible (requires ``REX_S3_BUCKET``, ``REX_S3_REGION``).

``REX_STORAGE_PATH`` (default: ``./backend_storage``)
    Root directory used by the ``local`` backend. Ignored by others.

``REX_S3_BUCKET``, ``REX_S3_REGION``, ``REX_S3_ENDPOINT_URL`` (optional)
    S3 adapter configuration. ``REX_S3_ENDPOINT_URL`` enables R2/MinIO
    compatibility. When ``REX_S3_BUCKET`` is absent the adapter raises
    ``StorageConfigError`` at construction time.

Any misconfiguration (unknown backend, unwritable local root, missing
bucket) raises a clear ``StorageConfigError`` at adapter construction.
This fails fast at startup rather than at first upload.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from pathlib import Path
from uuid import uuid4

DEFAULT_STORAGE_ROOT = Path(os.environ.get("REX_STORAGE_PATH", "./backend_storage"))


class StorageConfigError(RuntimeError):
    """Raised when storage configuration is invalid or unavailable.

    Distinct from ``FileNotFoundError`` / ``ValueError`` so the readiness
    endpoint and startup code can differentiate "not configured" from
    "file missing".
    """


# ── Adapter interface ─────────────────────────────────────────────────────


class StorageAdapter(ABC):
    """Minimal interface every storage backend must implement.

    Keys are opaque strings the caller persists in ``attachments.storage_key``.
    Adapters must treat all keys as untrusted — path traversal, nulls, and
    absolute paths must be rejected or neutralized by the adapter itself.
    """

    #: Identifier used in ``storage_url`` (e.g. ``local``, ``memory``, ``s3``).
    scheme: str = "unknown"

    @abstractmethod
    def make_key(self, project_id: str, filename: str) -> str:
        """Generate a fresh, unique, safe key for a new upload."""

    @abstractmethod
    def save(self, content: bytes, key: str) -> str:
        """Persist ``content`` at ``key``. Returns an opaque location string."""

    @abstractmethod
    def read(self, key: str) -> bytes:
        """Return stored bytes. Raises ``FileNotFoundError`` if missing."""

    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete ``key``. Returns True if something was removed."""

    def url_for(self, key: str) -> str:
        """Return a stable identifier for the attachments.storage_url column."""
        return f"{self.scheme}://{key}"

    def healthcheck(self) -> None:
        """Raise ``StorageConfigError`` if the adapter is not usable.

        Called by the readiness endpoint. Default is a no-op; filesystem
        adapters override to verify write access.
        """
        return None


# ── Local filesystem adapter ──────────────────────────────────────────────


class LocalStorageAdapter(StorageAdapter):
    """Filesystem-backed adapter suitable for single-host dev / on-prem.

    - Keys are relative paths under the configured root.
    - All keys are re-validated at read/save/delete time via ``_resolve_safe``
      so a hostile DB row cannot escape the root even if metadata was
      tampered with.
    """

    scheme = "local"

    def __init__(self, root: Path | None = None):
        try:
            self.root = (root or DEFAULT_STORAGE_ROOT).resolve()
            self.root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise StorageConfigError(
                f"Local storage root is not usable: {exc}"
            ) from exc

    def make_key(self, project_id: str, filename: str) -> str:
        # Strip path separators from filename to prevent traversal
        safe_name = Path(filename).name
        return f"attachments/{project_id}/{uuid4().hex}_{safe_name}"

    def _resolve_safe(self, key: str) -> Path:
        """Resolve ``key`` under ``self.root`` and reject escapes.

        Defends against path traversal even if a hostile DB row contains a
        storage_key like ``../../../etc/passwd``. Always re-validated at
        read/write time rather than trusting the column.
        """
        if not key or "\x00" in key:
            raise ValueError("Invalid storage key")
        candidate = (self.root / key).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("Storage key escapes storage root") from exc
        return candidate

    def save(self, content: bytes, key: str) -> str:
        path = self._resolve_safe(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return str(path)

    def read(self, key: str) -> bytes:
        path = self._resolve_safe(key)
        if not path.is_file():
            raise FileNotFoundError(key)
        return path.read_bytes()

    def delete(self, key: str) -> bool:
        try:
            path = self._resolve_safe(key)
        except ValueError:
            return False
        if not path.is_file():
            return False
        path.unlink()
        return True

    def healthcheck(self) -> None:
        """Verify the root is writable right now (readiness probe)."""
        probe = self.root / f".rex_readiness_{uuid4().hex}"
        try:
            probe.write_bytes(b"ok")
            probe.unlink()
        except OSError as exc:
            raise StorageConfigError(
                f"Storage root {self.root} is not writable: {exc}"
            ) from exc


# ── In-memory adapter (tests only) ────────────────────────────────────────


class MemoryStorageAdapter(StorageAdapter):
    """In-process dict-backed adapter for tests and ephemeral runs.

    Not registered as the default — opt in explicitly. Bytes live only
    as long as the adapter instance does.
    """

    scheme = "memory"

    def __init__(self):
        self._store: dict[str, bytes] = {}

    def make_key(self, project_id: str, filename: str) -> str:
        safe_name = Path(filename).name
        return f"attachments/{project_id}/{uuid4().hex}_{safe_name}"

    def save(self, content: bytes, key: str) -> str:
        if not key or "\x00" in key:
            raise ValueError("Invalid storage key")
        self._store[key] = content
        return f"memory://{key}"

    def read(self, key: str) -> bytes:
        if key not in self._store:
            raise FileNotFoundError(key)
        return self._store[key]

    def delete(self, key: str) -> bool:
        return self._store.pop(key, None) is not None


# ── S3/R2 adapter (production skeleton) ───────────────────────────────────


class S3StorageAdapter(StorageAdapter):
    """S3/R2-compatible adapter.

    Uses ``boto3`` when available, configured entirely via env vars:
    - ``REX_S3_BUCKET`` (required)
    - ``REX_S3_REGION`` (default ``us-east-1``)
    - ``REX_S3_ENDPOINT_URL`` (optional — set for R2 / MinIO)

    If ``boto3`` is not installed or the bucket env var is missing, the
    adapter raises ``StorageConfigError`` at construction — callers
    never reach the network layer.
    """

    scheme = "s3"

    def __init__(self):
        self.bucket = os.environ.get("REX_S3_BUCKET", "").strip()
        if not self.bucket:
            raise StorageConfigError(
                "S3 adapter requires REX_S3_BUCKET env var"
            )
        self.region = os.environ.get("REX_S3_REGION", "us-east-1").strip()
        self.endpoint_url = os.environ.get("REX_S3_ENDPOINT_URL", "").strip() or None
        try:
            import boto3  # type: ignore[import-untyped]
        except ImportError as exc:
            raise StorageConfigError(
                "S3 adapter requires boto3: pip install boto3"
            ) from exc

        kwargs: dict = {"region_name": self.region}
        if self.endpoint_url:
            kwargs["endpoint_url"] = self.endpoint_url
        self._client = boto3.client("s3", **kwargs)

    def make_key(self, project_id: str, filename: str) -> str:
        safe_name = Path(filename).name
        return f"attachments/{project_id}/{uuid4().hex}_{safe_name}"

    def save(self, content: bytes, key: str) -> str:
        if not key or "\x00" in key:
            raise ValueError("Invalid storage key")
        self._client.put_object(Bucket=self.bucket, Key=key, Body=content)
        return f"s3://{self.bucket}/{key}"

    def read(self, key: str) -> bytes:
        import botocore.exceptions  # type: ignore[import-untyped]
        try:
            resp = self._client.get_object(Bucket=self.bucket, Key=key)
            return resp["Body"].read()
        except botocore.exceptions.ClientError as exc:
            if exc.response["Error"]["Code"] in ("NoSuchKey", "404"):
                raise FileNotFoundError(key) from exc
            raise

    def delete(self, key: str) -> bool:
        self._client.delete_object(Bucket=self.bucket, Key=key)
        return True  # S3 delete is idempotent; no error means "gone"

    def url_for(self, key: str) -> str:
        return f"s3://{self.bucket}/{key}"

    def healthcheck(self) -> None:
        """Verify the bucket is reachable by issuing a HEAD request."""
        import botocore.exceptions  # type: ignore[import-untyped]
        try:
            self._client.head_bucket(Bucket=self.bucket)
        except botocore.exceptions.ClientError as exc:
            raise StorageConfigError(
                f"S3 bucket '{self.bucket}' is not reachable: {exc}"
            ) from exc


# ── Adapter registry + process-wide default ───────────────────────────────


_ADAPTER_REGISTRY: dict[str, type[StorageAdapter]] = {
    "local": LocalStorageAdapter,
    "memory": MemoryStorageAdapter,
    "s3": S3StorageAdapter,
}


def _build_adapter(backend: str) -> StorageAdapter:
    """Instantiate the adapter named ``backend`` or raise StorageConfigError."""
    cls = _ADAPTER_REGISTRY.get(backend)
    if cls is None:
        raise StorageConfigError(
            f"Unknown storage backend '{backend}'. "
            f"Supported: {sorted(_ADAPTER_REGISTRY)}"
        )
    return cls()


_default_adapter: StorageAdapter | None = None


def get_storage() -> StorageAdapter:
    """Return the process-wide storage adapter.

    Constructed lazily on first access using ``REX_STORAGE_BACKEND`` (default
    ``local``). Misconfiguration surfaces as ``StorageConfigError`` — callers
    should let it propagate at upload time, and the readiness endpoint should
    convert it into a 503.
    """
    global _default_adapter
    if _default_adapter is None:
        backend = os.environ.get("REX_STORAGE_BACKEND", "local").strip().lower()
        _default_adapter = _build_adapter(backend)
    return _default_adapter


def reset_storage(
    root: Path | None = None,
    backend: str | None = None,
) -> StorageAdapter:
    """Replace the process-wide adapter.

    Primarily used by tests to redirect to a tmp dir or the memory backend.
    If ``backend`` is given, instantiate that adapter (ignoring ``root`` unless
    it's the local backend). If only ``root`` is given, construct a new
    ``LocalStorageAdapter`` rooted there.
    """
    global _default_adapter
    if backend is not None:
        _default_adapter = _build_adapter(backend)
    else:
        _default_adapter = LocalStorageAdapter(root)
    return _default_adapter
