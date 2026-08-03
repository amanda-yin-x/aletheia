import hashlib
import json
import math
from typing import Any


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def content_hash(value: Any) -> str:
    data = value if isinstance(value, bytes) else canonical_json(value).encode()
    return hashlib.sha256(data).hexdigest()


def text_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def token_estimate(value: str) -> int:
    return math.ceil(len(value) / 4)

