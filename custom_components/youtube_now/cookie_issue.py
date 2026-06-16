from __future__ import annotations

from typing import Any

COOKIE_PROBLEM_ERROR_PATTERNS = (
    "refresh YouTube cookies",
    "ytInitialData was not found",
    "cookie file not found",
    "cookie load failed",
    "HTTP Error 401",
    "HTTP Error 403",
)
ATTR_ERROR = "error"
ATTR_VIDEO_ID = "video_id"


def cookie_fetch_succeeded(payload: dict[str, Any]) -> bool:
    """Return true when YouTube history was read successfully."""
    return bool(payload.get(ATTR_VIDEO_ID)) and not payload.get(ATTR_ERROR)


def cookie_repair_issue_reason(payload: dict[str, Any]) -> str | None:
    """Return the cookie problem reason, if this payload indicates one."""
    error = payload.get(ATTR_ERROR, "")
    if cookie_fetch_succeeded(payload):
        return None

    for pattern in COOKIE_PROBLEM_ERROR_PATTERNS:
        if pattern in error:
            return error

    return None
