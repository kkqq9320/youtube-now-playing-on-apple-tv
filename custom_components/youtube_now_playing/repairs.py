from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.components.repairs import RepairsFlow
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN
from .cookie_issue import cookie_fetch_succeeded, cookie_repair_issue_reason

COOKIE_REPAIR_ISSUE_PREFIX = "youtube_cookie_problem"


def cookie_repair_issue_id(entry_id: str) -> str:
    """Return the repair issue id for a config entry."""
    return f"{COOKIE_REPAIR_ISSUE_PREFIX}_{entry_id}"


async def async_update_cookie_repair_issue(
    hass: HomeAssistant,
    entry: ConfigEntry,
    cookie_file: str,
    payload: dict[str, Any],
) -> None:
    """Create or clear the cookie repair issue based on the latest payload."""
    issue_id = cookie_repair_issue_id(entry.entry_id)
    reason = cookie_repair_issue_reason(payload)

    if reason is not None:
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            is_fixable=True,
            is_persistent=True,
            severity=ir.IssueSeverity.ERROR,
            translation_key="youtube_cookie_problem",
            translation_placeholders={
                "cookie_file": cookie_file,
                "error": reason,
            },
            data={
                "entry_id": entry.entry_id,
                "cookie_file": cookie_file,
                "error": reason,
            },
        )
    elif cookie_fetch_succeeded(payload):
        ir.async_delete_issue(hass, DOMAIN, issue_id)


class YouTubeCookieRepairFlow(RepairsFlow):
    """Repair flow that rechecks the YouTube cookie file after manual renewal."""

    def __init__(
        self,
        hass: HomeAssistant,
        issue_id: str,
        data: dict[str, str | int | float | None] | None,
    ) -> None:
        """Initialize the repair flow."""
        self.hass = hass
        self.issue_id = issue_id
        self.data = data or {}

    async def async_step_init(
        self,
        user_input: dict[str, str] | None = None,
    ) -> data_entry_flow.FlowResult:
        """Handle the initial repair step."""
        return await self.async_step_confirm(user_input)

    async def async_step_confirm(
        self,
        user_input: dict[str, str] | None = None,
    ) -> data_entry_flow.FlowResult:
        """Refresh the integration once the cookie file has been replaced."""
        if user_input is None:
            return self.async_show_form(
                step_id="confirm",
                data_schema=vol.Schema({}),
                description_placeholders=self._description_placeholders(),
            )

        entry_id = str(self.data.get("entry_id") or "")
        coordinator = self.hass.data.get(DOMAIN, {}).get(entry_id)
        if coordinator is None:
            return self.async_abort(reason="entry_not_found")

        await coordinator.async_request_refresh()
        reason = cookie_repair_issue_reason(coordinator.data)
        if reason:
            return self.async_show_form(
                step_id="confirm",
                data_schema=vol.Schema({}),
                errors={"base": "still_invalid"},
                description_placeholders=self._description_placeholders(reason),
            )

        ir.async_delete_issue(self.hass, DOMAIN, self.issue_id)
        return self.async_create_entry(title="", data={})

    def _description_placeholders(self, error: str | None = None) -> dict[str, str]:
        """Return placeholders for the repair confirmation text."""
        return {
            "cookie_file": str(self.data.get("cookie_file") or ""),
            "error": str(error or self._current_error()),
        }

    def _current_error(self) -> str:
        """Return the latest known cookie issue error for this repair."""
        entry_id = str(self.data.get("entry_id") or "")
        coordinator = self.hass.data.get(DOMAIN, {}).get(entry_id)
        if coordinator is not None:
            reason = cookie_repair_issue_reason(coordinator.data)
            if reason:
                return reason

        return str(self.data.get("error") or "")


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create a repair flow for a YouTube Now Playing issue."""
    if issue_id.startswith(COOKIE_REPAIR_ISSUE_PREFIX):
        return YouTubeCookieRepairFlow(hass, issue_id, data)

    raise ValueError(f"Unknown issue id: {issue_id}")
