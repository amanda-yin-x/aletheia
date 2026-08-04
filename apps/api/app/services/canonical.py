import hashlib
import json
import math
from typing import Any

UTF8 = "utf-8"
CANONICAL_JSON_DESCRIPTION = (
    "UTF-8 RFC 8259 JSON with keys sorted lexicographically, no insignificant "
    "whitespace, Unicode preserved, and one trailing LF byte"
)


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def canonical_json_bytes(value: Any) -> bytes:
    """Return the one canonical on-disk representation used by build evidence.

    Build and report roots must describe bytes, rather than a Python value that
    could be serialized differently by an HTTP framework.  The trailing newline
    is intentional and is part of every JSON digest.
    """

    return (canonical_json(value) + "\n").encode(UTF8)


def canonical_json_text(value: Any) -> str:
    return canonical_json_bytes(value).decode(UTF8)


def artifact_bytes(value: Any) -> bytes:
    """Return the exact bytes served for a compiled artifact.

    Compiler artifacts are stored as UTF-8 strings.  Supporting structured
    values here keeps verification backwards-compatible with pre-root builds
    while still giving them an unambiguous canonical representation.
    """

    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        return value.encode(UTF8)
    return canonical_json_bytes(value)


def bytes_hash(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def artifact_hash(value: Any) -> str:
    return bytes_hash(artifact_bytes(value))


def content_hash(value: Any) -> str:
    data = value if isinstance(value, bytes) else canonical_json(value).encode()
    return hashlib.sha256(data).hexdigest()


def text_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def token_estimate(value: str) -> int:
    return math.ceil(len(value) / 4)
