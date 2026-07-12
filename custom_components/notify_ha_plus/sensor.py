"""Diagnostic sensors for Notify HA Plus - presence overview."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    CONF_TARGETS,
    DOMAIN,
    FIELD_DEVICE_TRACKER,
    FIELD_NAME,
    FIELD_PERSON_ENTITY,
    SIGNAL_OPTIONS_UPDATED,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up presence diagnostic sensors."""
    home_sensor = PresenceSensor(hass, entry, is_home=True)
    away_sensor = PresenceSensor(hass, entry, is_home=False)
    last_away_sensor = LastAwaySensor(hass, entry)

    async_add_entities([home_sensor, away_sensor, last_away_sensor])

    @callback
    def _on_options_updated() -> None:
        home_sensor.refresh_tracked_entities(entry)
        away_sensor.refresh_tracked_entities(entry)
        last_away_sensor.refresh_tracked_entities(entry)

    entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_OPTIONS_UPDATED, _on_options_updated)
    )


class PresenceSensor(SensorEntity):
    """Shows a comma-separated list of persons currently home or away."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _unsubscribe_tracker = None

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, *, is_home: bool) -> None:
        self._entry = entry
        self._is_home = is_home
        self._attr_unique_id = f"{entry.entry_id}_presence_{'home' if is_home else 'away'}"
        self._attr_name = "Anwesende Personen" if is_home else "Abwesende Personen"
        self._attr_icon = "mdi:home-account" if is_home else "mdi:home-remove"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Notify HA Plus",
            entry_type="service",
        )
        self._person_map: dict[str, dict] = {}
        self._build_person_map(entry)

    def _build_person_map(self, entry: ConfigEntry) -> None:
        """Build {person_entity: {name, tracker}} from current options."""
        self._person_map = {}
        for t in entry.options.get(CONF_TARGETS, []):
            pe = t.get(FIELD_PERSON_ENTITY)
            if pe:
                self._person_map[pe] = {
                    "name": t.get(FIELD_NAME, pe),
                    "tracker": t.get(FIELD_DEVICE_TRACKER),
                }

    def _is_person_home(self, person_entity: str) -> bool:
        state = self.hass.states.get(person_entity)
        if state and state.state == "home":
            return True
        info = self._person_map.get(person_entity, {})
        tracker = info.get("tracker")
        if tracker:
            ts = self.hass.states.get(tracker)
            if ts and ts.state == "home":
                return True
        return False

    def _compute_state(self) -> str:
        names = [
            info["name"]
            for pe, info in self._person_map.items()
            if self._is_person_home(pe) == self._is_home
        ]
        return ", ".join(sorted(names)) if names else "-"

    @property
    def native_value(self) -> str:
        return self._compute_state()

    @property
    def extra_state_attributes(self) -> dict:
        persons = [
            info["name"]
            for pe, info in self._person_map.items()
            if self._is_person_home(pe) == self._is_home
        ]
        return {"count": len(persons), "persons": sorted(persons)}

    async def async_added_to_hass(self) -> None:
        self._subscribe_to_changes()

    def _subscribe_to_changes(self) -> None:
        if self._unsubscribe_tracker:
            self._unsubscribe_tracker()

        tracked: list[str] = []
        for pe, info in self._person_map.items():
            tracked.append(pe)
            if info.get("tracker"):
                tracked.append(info["tracker"])

        if tracked:

            @callback
            def _state_changed(event: Event) -> None:
                self.async_write_ha_state()

            self._unsubscribe_tracker = async_track_state_change_event(
                self.hass, tracked, _state_changed
            )

    @callback
    def refresh_tracked_entities(self, entry: ConfigEntry) -> None:
        """Re-build person map and resubscribe after options change."""
        self._build_person_map(entry)
        self._subscribe_to_changes()
        self.async_write_ha_state()


class LastAwaySensor(SensorEntity):
    """Shows the person who was most recently marked as away."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _unsubscribe_tracker = None

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_presence_last_away"
        self._attr_name = "Zuletzt abwesend"
        self._attr_icon = "mdi:account-clock"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Notify HA Plus",
            entry_type="service",
        )
        self._person_map: dict[str, dict] = {}
        self._build_person_map(entry)

    def _build_person_map(self, entry: ConfigEntry) -> None:
        self._person_map = {}
        for t in entry.options.get(CONF_TARGETS, []):
            pe = t.get(FIELD_PERSON_ENTITY)
            if pe:
                self._person_map[pe] = {
                    "name": t.get(FIELD_NAME, pe),
                    "tracker": t.get(FIELD_DEVICE_TRACKER),
                }

    def _is_person_home(self, person_entity: str) -> bool:
        state = self.hass.states.get(person_entity)
        if state and state.state == "home":
            return True
        info = self._person_map.get(person_entity, {})
        tracker = info.get("tracker")
        if tracker:
            ts = self.hass.states.get(tracker)
            if ts and ts.state == "home":
                return True
        return False

    def _last_changed(self, person_entity: str):
        times = []
        state = self.hass.states.get(person_entity)
        if state:
            times.append(state.last_changed)
        info = self._person_map.get(person_entity, {})
        tracker = info.get("tracker")
        if tracker:
            ts = self.hass.states.get(tracker)
            if ts:
                times.append(ts.last_changed)
        return max(times) if times else None

    @property
    def native_value(self) -> str:
        away = [(pe, info) for pe, info in self._person_map.items() if not self._is_person_home(pe)]
        if not away:
            return "-"
        latest = max(away, key=lambda x: self._last_changed(x[0]) or 0)
        return latest[1]["name"]

    @property
    def extra_state_attributes(self) -> dict:
        away = [(pe, info) for pe, info in self._person_map.items() if not self._is_person_home(pe)]
        if not away:
            return {"person_entity": None, "last_changed": None}
        latest = max(away, key=lambda x: self._last_changed(x[0]) or 0)
        lc = self._last_changed(latest[0])
        return {
            "person_entity": latest[0],
            "last_changed": lc.isoformat() if lc else None,
        }

    async def async_added_to_hass(self) -> None:
        self._subscribe_to_changes()

    def _subscribe_to_changes(self) -> None:
        if self._unsubscribe_tracker:
            self._unsubscribe_tracker()
        tracked: list[str] = []
        for pe, info in self._person_map.items():
            tracked.append(pe)
            if info.get("tracker"):
                tracked.append(info["tracker"])
        if tracked:

            @callback
            def _state_changed(event: Event) -> None:
                self.async_write_ha_state()

            self._unsubscribe_tracker = async_track_state_change_event(
                self.hass, tracked, _state_changed
            )

    @callback
    def refresh_tracked_entities(self, entry: ConfigEntry) -> None:
        self._build_person_map(entry)
        self._subscribe_to_changes()
        self.async_write_ha_state()
