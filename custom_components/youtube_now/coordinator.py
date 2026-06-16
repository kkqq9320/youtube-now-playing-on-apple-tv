from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_COOKIE_FILE,
    CONF_MEDIA_PLAYER_ENTITY_ID,
    CONF_POLL_INTERVAL_SECONDS,
    DEFAULT_POLL_INTERVAL_SECONDS,
    DOMAIN,
    MAX_POLL_INTERVAL_SECONDS,
    MIN_POLL_INTERVAL_SECONDS,
)
from .youtube import fetch_latest_thumbnail, standalone_waiting_payload, waiting_payload


class YouTubeThumbnailCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator that fetches the latest YouTube history item on demand."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self.is_standalone = not entry.options.get(
            CONF_MEDIA_PLAYER_ENTITY_ID, entry.data.get(CONF_MEDIA_PLAYER_ENTITY_ID, "")
        )
        self.poll_interval_seconds = _entry_poll_interval_seconds(entry)
        super().__init__(
            hass,
            logger=__import__("logging").getLogger(__name__),
            name=DOMAIN,
            update_interval=(
                timedelta(seconds=self.poll_interval_seconds)
                if self.is_standalone
                else None
            ),
        )
        self.cookie_file = entry.options.get(
            CONF_COOKIE_FILE, entry.data[CONF_COOKIE_FILE]
        )
        self.data = (
            standalone_waiting_payload() if self.is_standalone else waiting_payload()
        )
        self.entry = entry

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch the latest history payload."""
        from .repairs import async_update_cookie_repair_issue

        payload = await self.hass.async_add_executor_job(
            fetch_latest_thumbnail, self.cookie_file
        )
        await async_update_cookie_repair_issue(
            self.hass,
            self.entry,
            self.cookie_file,
            payload,
        )
        return payload


def _entry_poll_interval_seconds(entry: ConfigEntry) -> int:
    """Return a normalized standalone polling interval from a config entry."""
    value = entry.options.get(
        CONF_POLL_INTERVAL_SECONDS,
        entry.data.get(CONF_POLL_INTERVAL_SECONDS, DEFAULT_POLL_INTERVAL_SECONDS),
    )
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        seconds = DEFAULT_POLL_INTERVAL_SECONDS

    return min(MAX_POLL_INTERVAL_SECONDS, max(MIN_POLL_INTERVAL_SECONDS, seconds))
