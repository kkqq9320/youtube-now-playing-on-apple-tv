from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er, selector

from .const import (
    CONF_COOKIE_FILE,
    CONF_CREATE_STANDALONE_SENSOR,
    CONF_MEDIA_PLAYER_ENTITY_ID,
    CONF_POLL_INTERVAL_SECONDS,
    CONF_YOUTUBE_APP_ID,
    DEFAULT_COOKIE_FILE,
    DEFAULT_POLL_INTERVAL_SECONDS,
    DEFAULT_YOUTUBE_APP_ID,
    DOMAIN,
    MAX_POLL_INTERVAL_SECONDS,
    MIN_POLL_INTERVAL_SECONDS,
    POLL_INTERVAL_STEP_SECONDS,
    STANDALONE_UNIQUE_ID,
)

MEDIA_PLAYER_DOMAIN = "media_player"


class YouTubeThumbnailConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for YouTube Now Playing."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return YouTubeThumbnailOptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Ask whether to create the standalone now playing sensor."""
        if user_input is not None:
            if not user_input[CONF_CREATE_STANDALONE_SENSOR]:
                return await self.async_step_media_player()

            return await self.async_step_standalone()

        return self.async_show_form(
            step_id="user",
            data_schema=_standalone_choice_schema(),
        )

    async def async_step_standalone(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the standalone now playing sensor setup step."""
        if user_input is not None:
            await self.async_set_unique_id(STANDALONE_UNIQUE_ID)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title="YouTube Now Playing",
                data=_normalize_user_input(user_input),
            )

        return self.async_show_form(
            step_id="standalone",
            data_schema=_standalone_settings_schema(),
        )

    async def async_step_media_player(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the Apple TV media player setup step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            entity_id = user_input[CONF_MEDIA_PLAYER_ENTITY_ID]
            data = _normalize_user_input(user_input)
            if entity_id and not _is_apple_tv_media_player(self.hass, entity_id):
                errors["base"] = "invalid_media_player"
            else:
                await self.async_set_unique_id(entity_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"YouTube Now Playing ({entity_id})",
                    data=data,
                )

        return self.async_show_form(
            step_id="media_player",
            data_schema=_media_player_schema(user_input),
            errors=errors,
        )


class YouTubeThumbnailOptionsFlow(config_entries.OptionsFlow):
    """Handle options for YouTube Now Playing."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage integration options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            entity_id = (user_input.get(CONF_MEDIA_PLAYER_ENTITY_ID) or "").strip()
            data = _normalize_user_input(user_input)
            if entity_id and not _is_apple_tv_media_player(self.hass, entity_id):
                errors["base"] = "invalid_media_player"
            else:
                return self.async_create_entry(title="", data=data)

        defaults = dict(self._config_entry.data)
        defaults.update(self._config_entry.options)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                _data_schema(defaults),
                _suggested_values(defaults),
            ),
            errors=errors,
        )


def _standalone_choice_schema() -> vol.Schema:
    """Build the standalone mode choice schema."""
    return vol.Schema(
        {
            vol.Required(CONF_CREATE_STANDALONE_SENSOR, default=False): (
                selector.BooleanSelector()
            )
        }
    )


def _standalone_settings_schema(
    defaults: dict[str, Any] | None = None,
) -> vol.Schema:
    """Build the standalone sensor settings schema."""
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_COOKIE_FILE,
                default=defaults.get(CONF_COOKIE_FILE, DEFAULT_COOKIE_FILE),
            ): selector.TextSelector(),
            vol.Required(
                CONF_POLL_INTERVAL_SECONDS,
                default=_poll_interval_value(defaults),
            ): _poll_interval_selector(),
        }
    )


def _media_player_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    """Build the required Apple TV media player setup schema."""
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(CONF_MEDIA_PLAYER_ENTITY_ID,
                description=_suggested_value(defaults, CONF_MEDIA_PLAYER_ENTITY_ID),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    integration="apple_tv",
                    domain=MEDIA_PLAYER_DOMAIN,
                )
            ),
            vol.Required(
                CONF_COOKIE_FILE,
                default=defaults.get(CONF_COOKIE_FILE, DEFAULT_COOKIE_FILE),
            ): selector.TextSelector(),
            vol.Optional(CONF_YOUTUBE_APP_ID,
                description=_suggested_value(defaults, CONF_YOUTUBE_APP_ID, DEFAULT_YOUTUBE_APP_ID),
            ): selector.TextSelector(),
        }
    )


def _data_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    """Build the config flow form schema."""
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Optional(
                CONF_MEDIA_PLAYER_ENTITY_ID,
                description=_suggested_value(defaults, CONF_MEDIA_PLAYER_ENTITY_ID),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    integration="apple_tv",
                    domain=MEDIA_PLAYER_DOMAIN,
                )
            ),
            vol.Required(
                CONF_COOKIE_FILE,
                default=defaults.get(CONF_COOKIE_FILE, DEFAULT_COOKIE_FILE),
            ): selector.TextSelector(),
            vol.Required(
                CONF_POLL_INTERVAL_SECONDS,
                default=_poll_interval_value(defaults),
            ): _poll_interval_selector(),
            vol.Optional(CONF_YOUTUBE_APP_ID,
                description=_suggested_value(
                    defaults, CONF_YOUTUBE_APP_ID, DEFAULT_YOUTUBE_APP_ID
                ),
            ): selector.TextSelector(),
        }
    )


def _normalize_user_input(user_input: dict[str, Any]) -> dict[str, Any]:
    """Normalize optional form values before storing config entry data."""
    entity_id = (user_input.get(CONF_MEDIA_PLAYER_ENTITY_ID) or "").strip()
    youtube_app_id = (user_input.get(CONF_YOUTUBE_APP_ID) or "").strip()

    data = {
        CONF_MEDIA_PLAYER_ENTITY_ID: entity_id,
        CONF_COOKIE_FILE: user_input[CONF_COOKIE_FILE],
        CONF_POLL_INTERVAL_SECONDS: _normalize_poll_interval_seconds(
            user_input.get(CONF_POLL_INTERVAL_SECONDS)
        ),
        CONF_YOUTUBE_APP_ID: youtube_app_id,
    }
    return data


def _poll_interval_selector() -> selector.NumberSelector:
    """Return the selector for standalone polling interval seconds."""
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=MIN_POLL_INTERVAL_SECONDS,
            max=MAX_POLL_INTERVAL_SECONDS,
            step=POLL_INTERVAL_STEP_SECONDS,
            mode="box",
            unit_of_measurement="s",
        )
    )


def _poll_interval_value(defaults: dict[str, Any]) -> int:
    """Return a normalized polling interval from stored defaults."""
    return _normalize_poll_interval_seconds(
        defaults.get(CONF_POLL_INTERVAL_SECONDS)
    )


def _normalize_poll_interval_seconds(value: Any) -> int:
    """Clamp the polling interval to a conservative supported range."""
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        seconds = DEFAULT_POLL_INTERVAL_SECONDS

    return min(
        MAX_POLL_INTERVAL_SECONDS,
        max(MIN_POLL_INTERVAL_SECONDS, seconds),
    )


def _suggested_value(
    defaults: dict[str, Any], key: str, fallback: str = ""
) -> dict[str, str]:
    """Return a suggested value only when the selector has a real value."""
    value = defaults.get(key) or fallback
    return {"suggested_value": value} if value else {}


def _suggested_values(defaults: dict[str, Any]) -> dict[str, Any]:
    """Return non-empty suggested values for Home Assistant's helper."""
    return {
        key: value
        for key, value in defaults.items()
        if value and key != CONF_MEDIA_PLAYER_ENTITY_ID
    }


def _is_apple_tv_media_player(hass, entity_id: str) -> bool:
    """Return true if the entity is an Apple TV media player."""
    registry = er.async_get(hass)
    entry = registry.async_get(entity_id)
    return (
        entry is not None
        and entry.domain == MEDIA_PLAYER_DOMAIN
        and entry.platform == "apple_tv"
    )
