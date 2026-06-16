from __future__ import annotations

from collections.abc import Mapping
from typing import Any

ATTR_APP_ID = "app_id"
ATTR_ENTITY_PICTURE = "entity_picture"
ATTR_MEDIA_TITLE = "media_title"
STATE_PAUSED = "paused"
STATE_PLAYING = "playing"
REFRESH_STATES = {STATE_PLAYING, STATE_PAUSED}


def should_fetch_for_state_change(
    old_state: str | None,
    old_attrs: Mapping[str, Any] | None,
    new_state: str | None,
    new_attrs: Mapping[str, Any] | None,
    youtube_app_id: str,
) -> bool:
    """Return true when an Apple TV YouTube state change should refresh history."""
    old_attrs = old_attrs or {}
    new_attrs = new_attrs or {}

    if new_state not in REFRESH_STATES:
        return False
    if new_attrs.get(ATTR_APP_ID) != youtube_app_id:
        return False
    if old_attrs.get(ATTR_APP_ID) != youtube_app_id:
        return True
    if old_state != new_state:
        return True
    if (
        new_state == STATE_PAUSED
        and old_attrs.get(ATTR_ENTITY_PICTURE)
        and not new_attrs.get(ATTR_ENTITY_PICTURE)
    ):
        return True

    return old_attrs.get(ATTR_MEDIA_TITLE) != new_attrs.get(ATTR_MEDIA_TITLE)


def should_patch_for_state_change(
    new_state: str | None,
    new_attrs: Mapping[str, Any] | None,
    youtube_app_id: str,
    thumbnail: str | None,
) -> bool:
    """Return true when the media player should be patched with the current thumbnail."""
    new_attrs = new_attrs or {}
    if not thumbnail:
        return False
    if new_state not in REFRESH_STATES:
        return False
    if new_attrs.get(ATTR_APP_ID) != youtube_app_id:
        return False

    return new_attrs.get(ATTR_ENTITY_PICTURE) != thumbnail
