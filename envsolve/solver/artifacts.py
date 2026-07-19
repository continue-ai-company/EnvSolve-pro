from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import os
from pathlib import Path
import tempfile


@dataclass(frozen=True)
class ImmutableArtifact:
    sha256: str
    path: str
    size_bytes: int

    def to_dict(self) -> dict[str, str | int]:
        return asdict(self)


class ImmutableArtifactStore:
    """Content-addressed storage for complete, redacted runtime evidence."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def put_text(self, value: str, *, suffix: str = ".txt") -> ImmutableArtifact:
        payload = value.encode("utf-8")
        digest = hashlib.sha256(payload).hexdigest()
        relative = Path(digest[:2]) / f"{digest}{suffix}"
        path = self.root / relative
        if not path.is_file():
            path.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary = tempfile.mkstemp(prefix=f".{digest}.", dir=path.parent)
            try:
                with os.fdopen(descriptor, "wb") as handle:
                    handle.write(payload)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, path)
            except BaseException:
                try:
                    os.unlink(temporary)
                except FileNotFoundError:
                    pass
                raise
        return ImmutableArtifact(digest, str(relative), len(payload))
