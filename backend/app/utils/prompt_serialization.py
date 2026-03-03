"""Utilities for linearizing nested JSON and emitting flat TOON payloads."""

from typing import Any, Dict, List, Optional, Tuple
import re


NUMBER_LIKE_PATTERN = re.compile(r"^[+-]?(?:\d+|\d+\.\d+|\.\d+)(?:[eE][+-]?\d+)?$")


def _normalize_scalar(value: Any) -> str:
    """Render primitive values consistently for linear key=value output."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    text = str(value)
    return text.replace("\n", "\\n")


def _sanitize_segment(segment: str) -> str:
    """Make path segments key-safe for flat TOON (`a.b.c` style keys)."""
    normalized = re.sub(r"[^A-Za-z0-9_]", "_", str(segment).strip())
    if not normalized:
        normalized = "k"
    if normalized[0].isdigit():
        normalized = f"k_{normalized}"
    return normalized


def _join_path(path: List[str]) -> str:
    if not path:
        return "value"
    return ".".join(path)


def _flatten(data: Any, path: List[str], items: List[Tuple[str, Any]]) -> None:
    if isinstance(data, dict):
        if not data:
            items.append((_join_path(path), "{}"))
            return
        for key in sorted(data.keys(), key=lambda k: str(k)):
            _flatten(data[key], [*path, _sanitize_segment(str(key))], items)
        return

    if isinstance(data, list):
        if not data:
            items.append((_join_path(path), "[]"))
            return
        for idx, value in enumerate(data):
            _flatten(value, [*path, f"i{idx}"], items)
        return

    items.append((_join_path(path), data))


def flatten_json(data: Any, prefix: str = "") -> List[Tuple[str, Any]]:
    """
    Flatten nested dict/list structures into dotted key paths.

    Example:
    {"a": {"b": [1, 2]}} -> [("a.b.i0", 1), ("a.b.i1", 2)]
    """
    items: List[Tuple[str, Any]] = []
    root_path = [_sanitize_segment(prefix)] if prefix else []
    _flatten(data, root_path, items)
    return items


def linearize_json(data: Any, prefix: str = "") -> str:
    """Convert nested JSON-like input into linear key=value lines."""
    flat = flatten_json(data, prefix=prefix)
    if not flat:
        return "value=null"
    return "\n".join(f"{key}={_normalize_scalar(value)}" for key, value in flat)


def _needs_quotes(value: str, delimiter: str = ",") -> bool:
    if value == "":
        return True
    if value != value.strip():
        return True
    if value in {"true", "false", "null"}:
        return True
    if NUMBER_LIKE_PATTERN.match(value):
        return True
    if any(ch in value for ch in [delimiter, ":", '"', "\\", "{", "}", "[", "]", "#"]):
        return True
    if any(ch in value for ch in ["\n", "\r", "\t"]):
        return True
    if value.startswith("-"):
        return True
    return False


def _escape_toon_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    escaped = escaped.replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
    return escaped


def _encode_toon_value(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)

    text = str(value)
    if _needs_quotes(text):
        return f"\"{_escape_toon_string(text)}\""
    return text


def json_to_toon(data: Any, root_key: Optional[str] = None) -> str:
    """
    Convert nested JSON-like input into flat (non-nested) TOON lines.

    Output intentionally has no indentation so it remains fully linear.
    """
    prefix = _sanitize_segment(root_key) if root_key else ""
    flat = flatten_json(data, prefix=prefix)
    if not flat:
        return "value: null"
    lines = [f"{key}: {_encode_toon_value(value)}" for key, value in flat]
    return "\n".join(lines)


def sections_to_toon(sections: Dict[str, Any]) -> str:
    """Convert multiple named sections into a single flat TOON document."""
    if not sections:
        return json_to_toon({}, "input")
    docs = [json_to_toon(value, root_key=name) for name, value in sections.items()]
    return "\n".join(line for doc in docs for line in doc.splitlines() if line.strip())


def is_flat_toon(toon_text: str) -> bool:
    """Return True if TOON text is linear (no nested indentation/list items)."""
    for line in toon_text.splitlines():
        if not line.strip():
            continue
        if line.startswith(" ") or line.startswith("\t"):
            return False
        if line.lstrip().startswith("- "):
            return False
    return True
