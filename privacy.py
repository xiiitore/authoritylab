""""Best-effort privacy redaction for audit events.

Redaction is a data-minimization layer, not a DLP guarantee. Callers should avoid
sending secrets or unnecessary personal data into the workflow in the first place.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

_REDACTED = "[REDACTED]"
_SENSITIVE_KEY = re.compile(
    r"(?:password|passwd|secret|token|apikey|accesskey|privatekey|clientsecret|"
    r"authorization|cookie|credential|sessionid|email|phone|address|dateofbirth|"
    r"socialsecurity|ssn|ipaddress|personaldata|userdata|fullname)",
    re.IGNORECASE,
)
_SENSITIVE_TEXT = (
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{8,}"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bnpm_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bpypi-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bya29\.[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"-----BEGIN (?:(?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY|ENCRYPTED PRIVATE KEY)-----.*?-----END (?:(?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY|ENCRYPTED PRIVATE KEY)-----", re.DOTALL),
    re.compile(r"(?i)(https?://)[^/@\s:]+:[^/@\s]+@"),
    re.compile(r"(?i)([?&](?:access_token|refresh_token|id_token|client_secret|client_assertion|api[_-]?key|token|secret|password|authorization|cookie|session(?:_id|id)?|private[_-]?key|signature)=)[^&#\s]+"),
    re.compile(r"(?i)\b(password|passwd|token|api[_-]?key|client[_-]?secret)\s*[:=]\s*[^\s,;]+"),
)


def redact_text(value: str) -> str:
    """Redact common credential patterns in free text; preserve other text."""
    if not isinstance(value, str):
        raise TypeError("value must be a string")
    result = value
    for pattern in _SENSITIVE_TEXT:
        if pattern.pattern.startswith("(?i)([?&]"):
            result = pattern.sub(r"\1[REDACTED]", result)
        elif pattern.pattern.startswith("(?i)\\b(password"):
            result = pattern.sub(lambda match: match.group(1) + "=[REDACTED]", result)
        elif pattern.pattern.startswith("(?i)(https"):
            result = pattern.sub(r"\1[REDACTED]@", result)
        elif pattern.pattern.startswith("(?i)\\bBearer"):
            result = pattern.sub("Bearer [REDACTED]", result)
        else:
            result = pattern.sub("[REDACTED]", result)
    return result


def redact_sensitive_data(value: Any, *, max_depth: int = 20) -> Any:
    """Return a JSON-shaped copy with sensitive keys and credential strings redacted.

    Non-JSON objects are represented by a type marker rather than arbitrary repr()
    output, which could itself contain secrets. Excessively nested values fail closed.
    """
    if type(max_depth) is not int or max_depth < 1:
        raise ValueError("max_depth must be a positive integer")

    def visit(item: Any, depth: int) -> Any:
        if depth >= max_depth:
            return "[MAX_DEPTH_REDACTED]"
        if isinstance(item, Mapping):
            cleaned: dict[str, Any] = {}
            for key, child in item.items():
                safe_key = redact_text(key) if isinstance(key, str) else "[NON_STRING_KEY]"
                normalized_key = re.sub(r"[^a-z0-9]", "", key.lower()) if isinstance(key, str) else ""
                if normalized_key and _SENSITIVE_KEY.search(normalized_key):
                    cleaned[safe_key] = _REDACTED
                else:
                    cleaned[safe_key] = visit(child, depth + 1)
            return cleaned
        if isinstance(item, (list, tuple)):
            return [visit(child, depth + 1) for child in item]
        if isinstance(item, str):
            return redact_text(item)
        if item is None or type(item) in (bool, int, float):
            return item
        return f"[NON_JSON_VALUE:{type(item).__name__}]"

    return visit(value, 0)
