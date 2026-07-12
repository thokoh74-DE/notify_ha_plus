"""Notify HA Plus - configurable, group-aware notification dispatcher."""

from __future__ import annotations

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.storage import Store

from .const import (
    ATTR_CRITICAL,
    ATTR_DASHBOARD_URL,
    ATTR_IMAGE_PATH,
    ATTR_LIVE_STREAM_URL,
    ATTR_MESSAGE,
    ATTR_PRIORITY,
    ATTR_SILENT,
    ATTR_TAG,
    ATTR_TARGET,
    ATTR_TITLE,
    ATTR_TTL,
    ATTR_VIDEO_PATH,
    DATA_ENTRY,
    DATA_LAST_NOTIFICATIONS,
    DATA_STORE,
    DOMAIN,
    PRIORITY_OPTIONS,
    SERVICE_SEND_NOTIFICATION,
)
from .dispatch import async_send_via_targets

STORAGE_KEY = f"{DOMAIN}.notifications"
STORAGE_VERSION = 1

PLATFORMS: list[str] = ["notify", "sensor"]

SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_TARGET): vol.All(cv.ensure_list, [cv.string]),
        vol.Required(ATTR_MESSAGE): cv.string,
        vol.Optional(ATTR_TITLE, default=""): cv.string,
        vol.Optional(ATTR_IMAGE_PATH, default=""): cv.string,
        vol.Optional(ATTR_VIDEO_PATH, default=""): cv.string,
        vol.Optional(ATTR_LIVE_STREAM_URL, default=""): cv.string,
        vol.Optional(ATTR_DASHBOARD_URL, default=""): cv.string,
        vol.Optional(ATTR_TAG, default=""): cv.string,
        vol.Optional(ATTR_TTL, default=0): vol.All(vol.Coerce(int), vol.Range(min=0, max=3600)),
        vol.Optional(ATTR_PRIORITY, default="high"): vol.In(PRIORITY_OPTIONS),
        vol.Required(ATTR_CRITICAL, default=False): cv.boolean,
        vol.Required(ATTR_SILENT, default=False): cv.boolean,
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Notify HA Plus from a config entry."""
    store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    stored_data = await store.async_load() or {}

    domain_data = hass.data.setdefault(DOMAIN, {})
    domain_data[DATA_ENTRY] = entry
    domain_data[DATA_STORE] = store
    domain_data[DATA_LAST_NOTIFICATIONS] = stored_data

    async def _handle_send(call: ServiceCall) -> None:
        d = call.data
        await async_send_via_targets(
            hass,
            entry,
            d[ATTR_TARGET],
            message=d[ATTR_MESSAGE],
            title=d[ATTR_TITLE],
            image_path=d[ATTR_IMAGE_PATH],
            video_path=d[ATTR_VIDEO_PATH],
            live_stream_url=d[ATTR_LIVE_STREAM_URL],
            dashboard_url=d[ATTR_DASHBOARD_URL],
            tag=d[ATTR_TAG],
            ttl=d[ATTR_TTL],
            priority=d[ATTR_PRIORITY],
            critical=d[ATTR_CRITICAL],
            silent=d[ATTR_SILENT],
            context=call.context,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_SEND_NOTIFICATION):
        hass.services.async_register(
            DOMAIN,
            SERVICE_SEND_NOTIFICATION,
            _handle_send,
            schema=SERVICE_SCHEMA,
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.services.async_remove(DOMAIN, SERVICE_SEND_NOTIFICATION)
        hass.data.pop(DOMAIN, None)
    return unloaded
