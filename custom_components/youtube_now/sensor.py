from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_CHANNEL,
    ATTR_COOKIES,
    ATTR_COOKIE_FILE,
    ATTR_DURATION_STRING,
    ATTR_ERROR,
    ATTR_ORIGINAL_URL,
    ATTR_POLL_INTERVAL_SECONDS,
    ATTR_TARGET_ENTITY_ID,
    ATTR_THUMBNAIL,
    ATTR_TITLE,
    ATTR_VIDEO_ID,
    ATTR_YOUTUBE_APP_ID,
    CONF_COOKIE_FILE,
    CONF_MEDIA_PLAYER_ENTITY_ID,
    CONF_POLL_INTERVAL_SECONDS,
    CONF_YOUTUBE_APP_ID,
    DEFAULT_POLL_INTERVAL_SECONDS,
    DOMAIN,
    STATE_NONE,
    STANDALONE_SENSOR_OBJECT_ID,
)
from .coordinator import YouTubeThumbnailCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the YouTube thumbnail sensor."""
    coordinator: YouTubeThumbnailCoordinator = hass.data[DOMAIN][entry.entry_id]
    media_player_entity_id = _entry_value(entry, CONF_MEDIA_PLAYER_ENTITY_ID)
    async_add_entities(
        [
            YouTubeWatchingSensor(
                coordinator,
                entry,
                media_player_entity_id,
                _target_device_info(hass, entry, media_player_entity_id),
            )
        ]
    )


def _entry_value(entry: ConfigEntry, key: str, default: Any = "") -> Any:
    """Return an option value, falling back to initial config data."""
    return entry.options.get(key, entry.data.get(key, default)) or default


def _fallback_device_info(entry: ConfigEntry) -> dict[str, Any]:
    """Return device info for a standalone YouTube Now Playing device."""
    return {
        "identifiers": {(DOMAIN, entry.entry_id)},
        "name": "YouTube Now Playing",
        "manufacturer": "YouTube",
    }


def _target_device_info(
    hass: HomeAssistant, entry: ConfigEntry, media_player_entity_id: str
) -> dict[str, Any]:
    """Return device info that joins the selected media player's device."""
    if not media_player_entity_id:
        return _fallback_device_info(entry)

    entity_registry = er.async_get(hass)
    media_player_registry_entry = entity_registry.async_get(media_player_entity_id)
    if (
        media_player_registry_entry is None
        or media_player_registry_entry.device_id is None
    ):
        return _fallback_device_info(entry)

    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get(media_player_registry_entry.device_id)
    if device_entry is None:
        return _fallback_device_info(entry)

    device_info: dict[str, Any] = {}
    if device_entry.identifiers:
        device_info["identifiers"] = set(device_entry.identifiers)
    if device_entry.connections:
        device_info["connections"] = set(device_entry.connections)

    return device_info or _fallback_device_info(entry)


class YouTubeWatchingSensor(CoordinatorEntity[YouTubeThumbnailCoordinator], SensorEntity):
    """Sensor that exposes the latest watched YouTube thumbnail and metadata."""

    _attr_icon = "mdi:youtube"
    _attr_name = "YouTube Watching"
    _attr_should_poll = False

    def __init__(
        self,
        coordinator: YouTubeThumbnailCoordinator,
        entry: ConfigEntry,
        media_player_entity_id: str,
        device_info: dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_watching"
        if media_player_entity_id:
            media_player_object_id = media_player_entity_id.split(".", 1)[-1]
            self.entity_id = f"sensor.youtube_now_{media_player_object_id}"
            self._attr_suggested_object_id = f"youtube_now_{media_player_object_id}"
        else:
            self.entity_id = "sensor.youtube_now_playing"
            self._attr_suggested_object_id = STANDALONE_SENSOR_OBJECT_ID
        self._attr_device_info = device_info
        self._entry = entry

    @property
    def native_value(self) -> str:
        """Return the thumbnail URL, or none when unavailable."""
        return self.coordinator.data.get(ATTR_THUMBNAIL) or STATE_NONE

    @property
    def entity_picture(self) -> str | None:
        """Return the thumbnail as the entity picture."""
        return self.coordinator.data.get(ATTR_THUMBNAIL) or None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return YouTube metadata."""
        data = self.coordinator.data
        return {
            ATTR_TARGET_ENTITY_ID: _entry_value(
                self._entry, CONF_MEDIA_PLAYER_ENTITY_ID
            ),
            ATTR_COOKIE_FILE: _entry_value(self._entry, CONF_COOKIE_FILE),
            ATTR_POLL_INTERVAL_SECONDS: _entry_value(
                self._entry,
                CONF_POLL_INTERVAL_SECONDS,
                DEFAULT_POLL_INTERVAL_SECONDS,
            ),
            ATTR_YOUTUBE_APP_ID: _entry_value(self._entry, CONF_YOUTUBE_APP_ID),
            ATTR_CHANNEL: data.get(ATTR_CHANNEL, ""),
            ATTR_TITLE: data.get(ATTR_TITLE, ""),
            ATTR_VIDEO_ID: data.get(ATTR_VIDEO_ID, ""),
            ATTR_DURATION_STRING: data.get(ATTR_DURATION_STRING, ""),
            ATTR_THUMBNAIL: data.get(ATTR_THUMBNAIL, ""),
            ATTR_ORIGINAL_URL: data.get(ATTR_ORIGINAL_URL, ""),
            ATTR_COOKIES: data.get(ATTR_COOKIES, False),
            ATTR_ERROR: data.get(ATTR_ERROR, ""),
        }
