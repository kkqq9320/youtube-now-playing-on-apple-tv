from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import Event, HomeAssistant, State

DELAYED_REFRESH_SECONDS = (1, 3, 6)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up YouTube Now Playing from a config entry."""
    from homeassistant.core import callback
    from homeassistant.helpers.event import async_call_later, async_track_state_change_event

    from .const import (
        ATTR_THUMBNAIL,
        CONF_MEDIA_PLAYER_ENTITY_ID,
        CONF_YOUTUBE_APP_ID,
        DOMAIN,
        PLATFORMS,
    )
    from .coordinator import YouTubeThumbnailCoordinator
    from .triggers import should_fetch_for_state_change, should_patch_for_state_change

    coordinator = YouTubeThumbnailCoordinator(hass, entry)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    media_player_entity_id = _entry_value(entry, CONF_MEDIA_PLAYER_ENTITY_ID)
    youtube_app_id = _entry_value(entry, CONF_YOUTUBE_APP_ID)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    if not media_player_entity_id:
        hass.async_create_task(coordinator.async_request_refresh())
        return True

    refresh_lock = asyncio.Lock()
    refresh_generation = 0
    delayed_refreshes: list[Callable[[], None]] = []

    @callback
    def cancel_callbacks(callbacks: list[Callable[[], None]]) -> None:
        """Cancel pending callbacks."""
        while callbacks:
            callbacks.pop()()

    @callback
    def current_state_is_youtube() -> bool:
        """Return true when the target media player is still showing YouTube."""
        state = hass.states.get(media_player_entity_id)
        return (
            state is not None
            and state.attributes.get("app_id") == youtube_app_id
            and state.state in {"playing", "paused"}
        )

    @callback
    def patch_current_thumbnail() -> None:
        """Patch the current fetched thumbnail if the target is still YouTube."""
        thumbnail = coordinator.data.get(ATTR_THUMBNAIL)
        if thumbnail and current_state_is_youtube():
            _patch_entity_picture(hass, media_player_entity_id, thumbnail)

    async def refresh_and_patch(version: int) -> None:
        """Refresh history, then patch only if this is the newest refresh sequence."""
        async with refresh_lock:
            await coordinator.async_request_refresh()
        if version != refresh_generation:
            return
        patch_current_thumbnail()

    @callback
    def start_refresh_sequence() -> None:
        """Start a refresh sequence and delayed follow-up fetches."""
        nonlocal refresh_generation

        refresh_generation += 1
        version = refresh_generation
        cancel_callbacks(delayed_refreshes)
        hass.async_create_task(refresh_and_patch(version))

        for delay in DELAYED_REFRESH_SECONDS:

            @callback
            def delayed_refresh(_now, scheduled_version=version) -> None:
                if scheduled_version == refresh_generation and current_state_is_youtube():
                    hass.async_create_task(refresh_and_patch(scheduled_version))

            delayed_refreshes.append(async_call_later(hass, delay, delayed_refresh))

    entry.async_on_unload(lambda: cancel_callbacks(delayed_refreshes))

    @callback
    def media_player_changed(event: Event) -> None:
        old_state: State | None = event.data.get("old_state")
        new_state: State | None = event.data.get("new_state")
        if new_state is None:
            return

        thumbnail = coordinator.data.get(ATTR_THUMBNAIL)
        if should_patch_for_state_change(
            new_state.state,
            new_state.attributes,
            youtube_app_id,
            thumbnail,
        ):
            patch_current_thumbnail()

        if not should_fetch_for_state_change(
            old_state.state if old_state else None,
            old_state.attributes if old_state else None,
            new_state.state,
            new_state.attributes,
            youtube_app_id,
        ):
            return

        start_refresh_sequence()

    entry.async_on_unload(
        async_track_state_change_event(
            hass, [media_player_entity_id], media_player_changed
        )
    )

    current_state = hass.states.get(media_player_entity_id)
    if current_state and should_fetch_for_state_change(
        None, None, current_state.state, current_state.attributes, youtube_app_id
    ):
        start_refresh_sequence()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    from .const import DOMAIN, PLATFORMS

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry when options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)


def _entry_value(entry: ConfigEntry, key: str, default: str = "") -> str:
    """Return an option value, falling back to initial config data."""
    return entry.options.get(key, entry.data.get(key, default)) or default


def _patch_entity_picture(
    hass: HomeAssistant, entity_id: str, entity_picture: str
) -> None:
    """Patch a media_player state representation with the YouTube thumbnail."""
    state = hass.states.get(entity_id)
    if state is None:
        return

    attributes = dict(state.attributes)
    if attributes.get("entity_picture") == entity_picture:
        return

    attributes["entity_picture"] = entity_picture
    hass.states.async_set(entity_id, state.state, attributes)
