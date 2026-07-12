"""Diagnostics support for Notify HA Plus."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_TARGETS,
    FIELD_DEVICE_TRACKER,
    FIELD_GROUPS,
    FIELD_NAME,
    FIELD_NOTIFY_SERVICE,
    FIELD_PERSON_ENTITY,
    FIELD_TYPE,
)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    targets = entry.options.get(CONF_TARGETS, [])
    return {
        "options": {k: v for k, v in entry.options.items() if k != CONF_TARGETS},
        "targets": [
            {
                FIELD_TYPE: t.get(FIELD_TYPE),
                FIELD_NAME: t.get(FIELD_NAME),
                FIELD_PERSON_ENTITY: t.get(FIELD_PERSON_ENTITY),
                FIELD_NOTIFY_SERVICE: t.get(FIELD_NOTIFY_SERVICE),
                FIELD_GROUPS: t.get(FIELD_GROUPS, []),
                FIELD_DEVICE_TRACKER: t.get(FIELD_DEVICE_TRACKER),
            }
            for t in targets
        ],
    }
