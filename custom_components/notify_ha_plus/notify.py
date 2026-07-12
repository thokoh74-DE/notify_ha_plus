"""Notify platform for Notify HA Plus.

Creates one entity per person/device/group/presence-keyword.  Entities serve
as pickable targets in the Automation UI's entity-selector AND track the
last notification timestamp + triggering automation.

Entities are dynamically rebuilt whenever the options change (dispatcher
signal), without requiring an integration reload.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.notify import NotifyEntity, NotifyEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_registry import async_get as er_async_get

from .const import (
    CONF_TARGETS,
    DATA_ADD_ENTITIES_CB,
    DATA_CURRENT_ENTITIES,
    DATA_ENTITY_TARGET_MAP,
    DATA_LAST_NOTIFICATIONS,
    DOMAIN,
    FIELD_GROUPS,
    FIELD_ID,
    FIELD_NAME,
    FIELD_NOTIFY_SERVICE,
    FIELD_PERSON_ENTITY,
    FIELD_TYPE,
    KEYWORD_AWAY,
    KEYWORD_HOME,
    KEYWORD_HOME_OR_LAST_AWAY,
    SIGNAL_NOTIFICATION_SENT,
    SIGNAL_OPTIONS_UPDATED,
)
from .dispatch import async_send_via_targets

_LOGGER = logging.getLogger(__name__)

SPECIAL_TARGET_NAMES = {
    KEYWORD_HOME: "Anwesende",
    KEYWORD_AWAY: "Abwesende",
    KEYWORD_HOME_OR_LAST_AWAY: "Anwesend oder zuletzt abwesend",
}


def _build_entity_specs(entry: ConfigEntry) -> list[dict[str, Any]]:
    """Derive the list of entities that should exist from the current options."""
    targets = entry.options.get(CONF_TARGETS, [])
    specs: list[dict[str, Any]] = []

    for t in targets:
        target_expr = (
            [t[FIELD_PERSON_ENTITY]] if t.get(FIELD_PERSON_ENTITY) else [t[FIELD_NOTIFY_SERVICE]]
        )
        is_person = t.get(FIELD_TYPE) == "person"
        specs.append(
            {
                "unique_suffix": f"target_{t[FIELD_ID]}",
                "name": t[FIELD_NAME],
                "target_expr": target_expr,
                "kind": "person" if is_person else "device",
                "person_entity": t.get(FIELD_PERSON_ENTITY) if is_person else None,
            }
        )

    group_names = sorted({g for t in targets for g in t.get(FIELD_GROUPS, [])})
    for group in group_names:
        specs.append(
            {
                "unique_suffix": f"group_{group}",
                "name": f"Gruppe: {group}",
                "target_expr": [group],
                "kind": "group",
                "person_entity": None,
            }
        )

    for keyword, label in SPECIAL_TARGET_NAMES.items():
        specs.append(
            {
                "unique_suffix": f"special_{keyword}",
                "name": label,
                "target_expr": [keyword],
                "kind": f"special_{keyword}",
                "person_entity": None,
            }
        )

    return specs


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up notify entities and register for dynamic updates."""
    store = hass.data.setdefault(DOMAIN, {})
    store[DATA_ADD_ENTITIES_CB] = async_add_entities
    store[DATA_CURRENT_ENTITIES] = {}
    store[DATA_ENTITY_TARGET_MAP] = {}

    _rebuild_entities(hass, entry)

    @callback
    def _on_options_updated() -> None:
        _rebuild_entities(hass, entry)

    entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_OPTIONS_UPDATED, _on_options_updated)
    )


@callback
def _rebuild_entities(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Diff current entities against desired specs, add new, remove stale."""
    store = hass.data.get(DOMAIN, {})
    add_cb: AddEntitiesCallback | None = store.get(DATA_ADD_ENTITIES_CB)
    current: dict[str, NotifyHaPlusEntity] = store.get(DATA_CURRENT_ENTITIES, {})
    entity_map: dict[str, list[str]] = store.setdefault(DATA_ENTITY_TARGET_MAP, {})

    if add_cb is None:
        return

    specs = _build_entity_specs(entry)
    desired_keys = {s["unique_suffix"] for s in specs}
    current_keys = set(current.keys())

    # Remove stale entities
    registry = er_async_get(hass)
    for key in current_keys - desired_keys:
        ent = current.pop(key, None)
        if ent and ent.entity_id:
            entity_map.pop(ent.entity_id, None)
            if registry.async_get(ent.entity_id):
                registry.async_remove(ent.entity_id)

    # Add new entities
    new_entities: list[NotifyHaPlusEntity] = []
    for spec in specs:
        if spec["unique_suffix"] not in current_keys:
            ent = NotifyHaPlusEntity(
                entry,
                unique_suffix=spec["unique_suffix"],
                name=spec["name"],
                target_expr=spec["target_expr"],
                kind=spec["kind"],
                person_entity=spec.get("person_entity"),
            )
            current[spec["unique_suffix"]] = ent
            new_entities.append(ent)

    if new_entities:
        add_cb(new_entities)

    store[DATA_CURRENT_ENTITIES] = current


ICON_MAP = {
    "person": "mdi:account",
    "device": "mdi:speaker",
    "group": "mdi:account-group",
    "special_home": "mdi:home-account",
    "special_away": "mdi:account-arrow-right",
    "special_home_or_last_away": "mdi:account-clock",
}


class NotifyHaPlusEntity(NotifyEntity):
    """A pickable notify target backed by Notify HA Plus target resolution."""

    _attr_has_entity_name = True
    _attr_supported_features = NotifyEntityFeature.TITLE

    def __init__(
        self,
        entry: ConfigEntry,
        unique_suffix: str,
        name: str,
        target_expr: list[str],
        kind: str = "device",
        person_entity: str | None = None,
    ) -> None:
        self._entry = entry
        self._target_expr = target_expr
        self._kind = kind
        self._person_entity_id = person_entity
        self._attr_unique_id = f"{entry.entry_id}_{unique_suffix}"
        self._attr_name = name
        self._attr_icon = ICON_MAP.get(kind, "mdi:bell")
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Notify HA Plus",
            entry_type="service",
        )

    @property
    def target_expr(self) -> list[str]:
        return self._target_expr

    @property
    def entity_picture(self) -> str | None:
        """For person targets, show their HA profile picture."""
        if self._kind == "person" and self._person_entity_id:
            state = self.hass.states.get(self._person_entity_id)
            if state:
                return state.attributes.get("entity_picture")
        return None

    async def async_added_to_hass(self) -> None:
        """Register entity_id → target_expr mapping and listen for updates."""
        store = self.hass.data.setdefault(DOMAIN, {})
        entity_map: dict[str, list[str]] = store.setdefault(DATA_ENTITY_TARGET_MAP, {})
        entity_map[self.entity_id] = self._target_expr

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_NOTIFICATION_SENT, self._on_notification_sent
            )
        )

    @callback
    def _on_notification_sent(self) -> None:
        """Re-render state when any notification was sent."""
        self.async_write_ha_state()

    @property
    def state(self) -> str | None:
        """Return timestamp of last notification from the shared store."""
        store = self.hass.data.get(DOMAIN, {})
        notifications: dict[str, dict] = store.get(DATA_LAST_NOTIFICATIONS, {})
        for key in self._target_expr:
            info = notifications.get(key)
            if info:
                return info.get("timestamp")
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Show last notification details as attributes."""
        store = self.hass.data.get(DOMAIN, {})
        notifications: dict[str, dict] = store.get(DATA_LAST_NOTIFICATIONS, {})
        for key in self._target_expr:
            info = notifications.get(key)
            if info:
                return {
                    "last_automation": info.get("automation") or "-",
                    "last_message": info.get("message") or "",
                }
        return None

    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Send notification and record it."""
        await async_send_via_targets(
            self.hass,
            self._entry,
            self._target_expr,
            message=message,
            title=title or "",
            context=self._context,
        )
        self._async_record_notification()
