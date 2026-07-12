"""Shared target resolution and dispatch logic for Notify HA Plus."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util import dt as dt_util

from .const import (
    ALEXA_MEDIA_PLAYER_PREFIX,
    ALEXA_NOTIFY_PREFIX,
    CONF_SILENT_CHANNEL,
    CONF_TARGETS,
    CONF_VOLUME_AFTER,
    CONF_VOLUME_CRITICAL,
    CONF_VOLUME_NORMAL,
    DATA_ENTITY_TARGET_MAP,
    DATA_LAST_NOTIFICATIONS,
    DATA_STORE,
    DEFAULT_SILENT_CHANNEL,
    DEFAULT_VOLUME_AFTER,
    DEFAULT_VOLUME_CRITICAL,
    DEFAULT_VOLUME_NORMAL,
    DOMAIN,
    FIELD_DEVICE_TRACKER,
    FIELD_GROUPS,
    FIELD_NOTIFY_SERVICE,
    FIELD_PERSON_ENTITY,
    KEYWORD_AWAY,
    KEYWORD_HOME,
    KEYWORD_HOME_OR_LAST_AWAY,
    SIGNAL_NOTIFICATION_SENT,
)

_LOGGER = logging.getLogger(__name__)


def find_triggering_automation(hass: HomeAssistant, context: Context | None) -> str | None:
    """Try to determine which automation/script triggered this call."""
    if not context or not context.parent_id:
        return None
    for domain in ("automation", "script"):
        for state in hass.states.async_all(domain):
            if state.context and state.context.id == context.parent_id:
                return state.attributes.get("friendly_name") or state.entity_id
    return None


def _expand_own_entities(hass: HomeAssistant, target: list[str]) -> list[str]:
    """Replace own notify.* entity_ids with their underlying target expressions."""
    entity_map: dict[str, list[str]] = hass.data.get(DOMAIN, {}).get(DATA_ENTITY_TARGET_MAP, {})
    expanded: list[str] = []
    for item in target:
        if item in entity_map:
            expanded.extend(entity_map[item])
        else:
            expanded.append(item)
    return expanded


def resolve_targets(hass: HomeAssistant, entry: ConfigEntry, target: list[str]) -> list[str]:
    """Resolve target list into de-duplicated list of notify.* services."""
    target = _expand_own_entities(hass, target)
    all_targets = entry.options.get(CONF_TARGETS, [])
    persons = [t for t in all_targets if t.get(FIELD_PERSON_ENTITY)]

    def _is_home(person: dict) -> bool:
        state = hass.states.get(person[FIELD_PERSON_ENTITY])
        if state and state.state == "home":
            return True
        tracker = person.get(FIELD_DEVICE_TRACKER)
        if tracker:
            ts = hass.states.get(tracker)
            if ts and ts.state == "home":
                return True
        return False

    def _last_changed(person: dict):
        times = []
        state = hass.states.get(person[FIELD_PERSON_ENTITY])
        if state:
            times.append(state.last_changed)
        tracker = person.get(FIELD_DEVICE_TRACKER)
        if tracker:
            ts = hass.states.get(tracker)
            if ts:
                times.append(ts.last_changed)
        return max(times) if times else None

    home_persons = [p for p in persons if _is_home(p)]
    away_persons = [p for p in persons if not _is_home(p)]
    resolved: list[str] = []

    for item in target:
        if item == KEYWORD_HOME:
            resolved += [p[FIELD_NOTIFY_SERVICE] for p in home_persons]
        elif item == KEYWORD_AWAY:
            resolved += [p[FIELD_NOTIFY_SERVICE] for p in away_persons]
        elif item == KEYWORD_HOME_OR_LAST_AWAY:
            if home_persons:
                resolved += [p[FIELD_NOTIFY_SERVICE] for p in home_persons]
            elif away_persons:
                last = max(away_persons, key=lambda p: _last_changed(p) or 0)
                resolved.append(last[FIELD_NOTIFY_SERVICE])
        elif item.startswith("notify."):
            resolved.append(item)
        elif item.startswith("person."):
            match = next((p for p in persons if p[FIELD_PERSON_ENTITY] == item), None)
            if match:
                resolved.append(match[FIELD_NOTIFY_SERVICE])
            else:
                _LOGGER.warning("notify_ha_plus: person %s not configured", item)
        else:
            group_matches = [
                t[FIELD_NOTIFY_SERVICE] for t in all_targets if item in t.get(FIELD_GROUPS, [])
            ]
            if not group_matches:
                _LOGGER.warning("notify_ha_plus: unknown group '%s'", item)
            resolved += group_matches

    seen: set[str] = set()
    unique: list[str] = []
    for svc in resolved:
        if svc not in seen:
            seen.add(svc)
            unique.append(svc)
    return unique


def record_notification(
    hass: HomeAssistant,
    target_keys: list[str],
    message: str,
    automation_name: str | None,
) -> None:
    """Store last-notification metadata for each target key (used by entities).

    Writes to both hass.data (for immediate entity updates) and to the
    persistent Store (survives HA restarts).
    """
    domain_data = hass.data.setdefault(DOMAIN, {})
    notifications: dict[str, dict[str, Any]] = domain_data.setdefault(DATA_LAST_NOTIFICATIONS, {})
    now = dt_util.utcnow().isoformat()
    info = {
        "timestamp": now,
        "automation": automation_name,
        "message": (message[:80] + "…") if len(message) > 80 else message,
    }
    for key in target_keys:
        notifications[key] = info
    async_dispatcher_send(hass, SIGNAL_NOTIFICATION_SENT)

    # Persist to disk so data survives restarts
    store = domain_data.get(DATA_STORE)
    if store:
        hass.async_create_task(store.async_save(dict(notifications)))


async def async_send_via_targets(
    hass: HomeAssistant,
    entry: ConfigEntry,
    target: list[str],
    *,
    message: str,
    title: str = "",
    image_path: str = "",
    video_path: str = "",
    live_stream_url: str = "",
    dashboard_url: str = "",
    tag: str = "",
    ttl: int = 0,
    priority: str = "high",
    critical: bool = False,
    silent: bool = False,
    context: Context | None = None,
) -> None:
    """Resolve targets and dispatch the notification."""
    resolved_targets = resolve_targets(hass, entry, target)
    if not resolved_targets:
        raise HomeAssistantError(f"notify_ha_plus: no target resolved from {target!r}")

    automation_name = find_triggering_automation(hass, context)

    # Record under the expanded target keys (group/person/keyword names)
    # so the matching entities can find their timestamp.
    expanded = _expand_own_entities(hass, target)
    record_keys = list(expanded)

    # Also record under each individual person/device that was actually
    # resolved, so that e.g. sending to group "Admin" also updates Thomas.
    all_cfg = entry.options.get(CONF_TARGETS, [])
    for svc in resolved_targets:
        for t in all_cfg:
            if t.get(FIELD_NOTIFY_SERVICE) == svc:
                pe = t.get(FIELD_PERSON_ENTITY)
                if pe and pe not in record_keys:
                    record_keys.append(pe)
                ns = t.get(FIELD_NOTIFY_SERVICE)
                if ns and ns not in record_keys:
                    record_keys.append(ns)

    record_notification(hass, record_keys, message, automation_name)

    push_dict: dict[str, Any] = {}
    if critical:
        push_dict["sound"] = {"name": "default", "critical": 1, "volume": 1.0}

    actions: list[dict[str, str]] = []
    if live_stream_url:
        actions.append({"action": "URI", "title": "Livestream öffnen", "uri": live_stream_url})
    if dashboard_url:
        actions.append({"action": "URI", "title": "Live ansehen", "uri": dashboard_url})

    notify_payload: dict[str, Any] = {}
    if title:
        notify_payload["title"] = title
    notify_payload["message"] = message

    payload_data: dict[str, Any] = {
        "ttl": ttl,
        "priority": priority,
        "visibility": "public",
    }
    if silent and not critical:
        # Android: custom channel; user disables sound once in
        # Android Settings → Apps → HA Companion → Notifications → channel
        silent_channel = entry.options.get(CONF_SILENT_CHANNEL, DEFAULT_SILENT_CHANNEL)
        payload_data["channel"] = silent_channel
        payload_data["importance"] = "high"
        # iOS: show alert + badge but omit sound from presentation_options
        payload_data["presentation_options"] = ["alert", "badge"]
    else:
        payload_data["channel"] = "HomeAssistant"
    if image_path:
        payload_data["image"] = image_path
    if video_path:
        payload_data["video"] = video_path
    if tag:
        payload_data["tag"] = tag
    if push_dict:
        payload_data["push"] = push_dict
    if actions:
        payload_data["actions"] = actions
    notify_payload["data"] = payload_data

    alexa_players = [
        svc.replace(ALEXA_NOTIFY_PREFIX, ALEXA_MEDIA_PLAYER_PREFIX)
        for svc in resolved_targets
        if svc.startswith(ALEXA_NOTIFY_PREFIX)
    ]
    vol_normal = entry.options.get(CONF_VOLUME_NORMAL, DEFAULT_VOLUME_NORMAL)
    vol_critical = entry.options.get(CONF_VOLUME_CRITICAL, DEFAULT_VOLUME_CRITICAL)
    vol_after = entry.options.get(CONF_VOLUME_AFTER, DEFAULT_VOLUME_AFTER)
    vol_before = vol_critical if critical else vol_normal

    if alexa_players:
        await asyncio.gather(
            *[
                hass.services.async_call(
                    "media_player",
                    "volume_set",
                    {"volume_level": vol_before},
                    target={"entity_id": eid},
                )
                for eid in alexa_players
            ]
        )

    async def _dispatch(service: str) -> None:
        domain, _, svc_name = service.partition(".")
        try:
            await hass.services.async_call(domain, svc_name, notify_payload)
        except HomeAssistantError as err:
            _LOGGER.error("notify_ha_plus: %s failed: %s", service, err)

    await asyncio.gather(*[_dispatch(svc) for svc in resolved_targets])

    if alexa_players:
        await asyncio.sleep(5)
        await asyncio.gather(
            *[
                hass.services.async_call(
                    "media_player",
                    "volume_set",
                    {"volume_level": vol_after},
                    target={"entity_id": eid},
                )
                for eid in alexa_players
            ]
        )
