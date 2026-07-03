from __future__ import annotations

import hashlib
import json


def stable_content_hash(payload: dict[str, object], text: str | None) -> str:
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    content = f"{serialized}\n{text or ''}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()

