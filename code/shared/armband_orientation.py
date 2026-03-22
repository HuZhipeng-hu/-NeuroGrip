"""Helpers for explicit armband orientation metadata."""

from __future__ import annotations

from typing import Any

_ALIASES = {
    "normal": "normal",
    "forward": "normal",
    "front": "normal",
    "正": "normal",
    "正戴": "normal",
    "flipped": "flipped",
    "reverse": "flipped",
    "reversed": "flipped",
    "backward": "flipped",
    "back": "flipped",
    "反": "flipped",
    "反戴": "flipped",
    "unknown": "unknown",
    "unspecified": "unknown",
    "": "unknown",
}


def normalize_armband_orientation(value: Any) -> str:
    token = str(value or "").strip().lower()
    return _ALIASES.get(token, token or "unknown")
