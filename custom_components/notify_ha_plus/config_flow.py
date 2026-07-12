"""Config and Options flow for Notify HA Plus.

The ConfigFlow walks the user through initial setup (add persons, devices,
groups) before creating the config entry.  The OptionsFlow re-uses the
same form logic for later edits.  Shared logic lives in _SharedFlowMixin.
"""

from __future__ import annotations

import uuid
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    CONF_SILENT_CHANNEL,
    CONF_TARGETS,
    CONF_VOLUME_AFTER,
    CONF_VOLUME_CRITICAL,
    CONF_VOLUME_NORMAL,
    DEFAULT_SILENT_CHANNEL,
    DEFAULT_VOLUME_AFTER,
    DEFAULT_VOLUME_CRITICAL,
    DEFAULT_VOLUME_NORMAL,
    DOMAIN,
    EXCLUDED_NOTIFY_SERVICES,
    FIELD_DEVICE_TRACKER,
    FIELD_GROUPS,
    FIELD_ID,
    FIELD_NAME,
    FIELD_NOTIFY_SERVICE,
    FIELD_PERSON_ENTITY,
    FIELD_TYPE,
    SIGNAL_OPTIONS_UPDATED,
    TARGET_TYPE_DEVICE,
    TARGET_TYPE_PERSON,
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Shared form logic used by both ConfigFlow and OptionsFlow
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class _SharedFlowMixin:
    """Methods shared between ConfigFlow (initial setup) and OptionsFlow."""

    _targets: list[dict[str, Any]]
    _volume: dict[str, Any]
    _selected_target_id: str | None

    def _notify_service_options(self) -> list[selector.SelectOptionDict]:
        services = self.hass.services.async_services().get("notify", {})
        return [
            selector.SelectOptionDict(value=f"notify.{name}", label=name)
            for name in sorted(services)
            if name not in EXCLUDED_NOTIFY_SERVICES
        ]

    def _existing_group_options(self) -> list[str]:
        groups: set[str] = set()
        for target in self._targets or []:
            groups.update(target.get(FIELD_GROUPS, []))
        return sorted(groups)

    def _group_selector(self, default: list[str]) -> vol.Optional:
        return vol.Optional(FIELD_GROUPS, default=default)

    # --------------------------------------------------------- add person
    async def _do_add_person(
        self, user_input: dict[str, Any] | None, *, return_step
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}
        existing_persons = {
            t[FIELD_PERSON_ENTITY] for t in self._targets if t[FIELD_TYPE] == TARGET_TYPE_PERSON
        }

        if user_input is not None:
            person_entity = user_input[FIELD_PERSON_ENTITY]
            if person_entity in existing_persons:
                errors[FIELD_PERSON_ENTITY] = "person_already_added"
            else:
                state = self.hass.states.get(person_entity)
                name = state.name if state else person_entity
                self._targets.append(
                    {
                        FIELD_ID: uuid.uuid4().hex,
                        FIELD_TYPE: TARGET_TYPE_PERSON,
                        FIELD_NAME: name,
                        FIELD_PERSON_ENTITY: person_entity,
                        FIELD_NOTIFY_SERVICE: user_input[FIELD_NOTIFY_SERVICE],
                        FIELD_GROUPS: user_input.get(FIELD_GROUPS, []),
                        FIELD_DEVICE_TRACKER: user_input.get(FIELD_DEVICE_TRACKER),
                    }
                )
                self._on_data_changed()
                return await return_step()

        schema = vol.Schema(
            {
                vol.Required(FIELD_PERSON_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="person")
                ),
                vol.Required(FIELD_NOTIFY_SERVICE): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=self._notify_service_options(),
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                self._group_selector([]): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=self._existing_group_options(),
                        multiple=True,
                        custom_value=True,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(FIELD_DEVICE_TRACKER): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="device_tracker")
                ),
            }
        )
        return self.async_show_form(step_id="add_person", data_schema=schema, errors=errors)

    # --------------------------------------------------------- add device
    async def _do_add_device(
        self, user_input: dict[str, Any] | None, *, return_step
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            self._targets.append(
                {
                    FIELD_ID: uuid.uuid4().hex,
                    FIELD_TYPE: TARGET_TYPE_DEVICE,
                    FIELD_NAME: user_input[FIELD_NAME],
                    FIELD_PERSON_ENTITY: None,
                    FIELD_NOTIFY_SERVICE: user_input[FIELD_NOTIFY_SERVICE],
                    FIELD_GROUPS: user_input.get(FIELD_GROUPS, []),
                    FIELD_DEVICE_TRACKER: None,
                }
            )
            self._on_data_changed()
            return await return_step()

        schema = vol.Schema(
            {
                vol.Required(FIELD_NAME): selector.TextSelector(),
                vol.Required(FIELD_NOTIFY_SERVICE): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=self._notify_service_options(),
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                self._group_selector([]): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=self._existing_group_options(),
                        multiple=True,
                        custom_value=True,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )
        return self.async_show_form(step_id="add_device", data_schema=schema)

    # ------------------------------------------------------ manage targets
    async def _do_manage_targets(
        self, user_input: dict[str, Any] | None, *, return_step
    ) -> config_entries.ConfigFlowResult:
        if not self._targets:
            if user_input is not None:
                return await return_step()
            return self.async_show_form(
                step_id="manage_targets",
                data_schema=vol.Schema({}),
                errors={"base": "no_targets"},
            )

        if user_input is not None:
            self._selected_target_id = user_input["target_id"]
            return await self.async_step_edit_target()

        options = [
            selector.SelectOptionDict(
                value=t[FIELD_ID],
                label=f"{t[FIELD_NAME]} ({', '.join(t.get(FIELD_GROUPS, [])) or '-'})",
            )
            for t in self._targets
        ]
        return self.async_show_form(
            step_id="manage_targets",
            data_schema=vol.Schema(
                {
                    vol.Required("target_id"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=options,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )

    async def _do_edit_target(
        self, user_input: dict[str, Any] | None, *, return_step
    ) -> config_entries.ConfigFlowResult:
        target = next(
            (t for t in self._targets if t[FIELD_ID] == self._selected_target_id),
            None,
        )
        if target is None:
            return await return_step()

        if user_input is not None:
            if user_input.get("remove"):
                self._targets = [t for t in self._targets if t[FIELD_ID] != target[FIELD_ID]]
            else:
                target[FIELD_NOTIFY_SERVICE] = user_input[FIELD_NOTIFY_SERVICE]
                target[FIELD_GROUPS] = user_input.get(FIELD_GROUPS, [])
                if target[FIELD_TYPE] == TARGET_TYPE_PERSON:
                    target[FIELD_DEVICE_TRACKER] = user_input.get(FIELD_DEVICE_TRACKER)
            self._on_data_changed()
            return await return_step()

        schema_dict: dict[Any, Any] = {
            vol.Required(
                FIELD_NOTIFY_SERVICE, default=target[FIELD_NOTIFY_SERVICE]
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=self._notify_service_options(),
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            self._group_selector(target.get(FIELD_GROUPS, [])): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=self._existing_group_options(),
                    multiple=True,
                    custom_value=True,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
        }
        if target[FIELD_TYPE] == TARGET_TYPE_PERSON:
            dt = target.get(FIELD_DEVICE_TRACKER)
            key = (
                vol.Optional(FIELD_DEVICE_TRACKER, default=dt)
                if dt
                else vol.Optional(FIELD_DEVICE_TRACKER)
            )
            schema_dict[key] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="device_tracker")
            )
        schema_dict[vol.Optional("remove", default=False)] = selector.BooleanSelector()
        return self.async_show_form(
            step_id="edit_target",
            data_schema=vol.Schema(schema_dict),
            description_placeholders={"name": target[FIELD_NAME]},
        )

    # ------------------------------------------------------ volume / channel
    async def _do_volume_settings(
        self, user_input: dict[str, Any] | None, *, return_step
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            self._volume = {
                CONF_VOLUME_NORMAL: user_input[CONF_VOLUME_NORMAL],
                CONF_VOLUME_CRITICAL: user_input[CONF_VOLUME_CRITICAL],
                CONF_VOLUME_AFTER: user_input[CONF_VOLUME_AFTER],
                CONF_SILENT_CHANNEL: user_input[CONF_SILENT_CHANNEL],
            }
            self._on_data_changed()
            return await return_step()

        def number_sel():
            return selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=1, step=0.05, mode=selector.NumberSelectorMode.SLIDER
                )
            )

        return self.async_show_form(
            step_id="volume_settings",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_VOLUME_NORMAL, default=self._volume[CONF_VOLUME_NORMAL]
                    ): number_sel(),
                    vol.Required(
                        CONF_VOLUME_CRITICAL, default=self._volume[CONF_VOLUME_CRITICAL]
                    ): number_sel(),
                    vol.Required(
                        CONF_VOLUME_AFTER, default=self._volume[CONF_VOLUME_AFTER]
                    ): number_sel(),
                    vol.Required(
                        CONF_SILENT_CHANNEL,
                        default=self._volume.get(CONF_SILENT_CHANNEL, DEFAULT_SILENT_CHANNEL),
                    ): selector.TextSelector(),
                }
            ),
        )

    def _build_options(self) -> dict[str, Any]:
        return {CONF_TARGETS: self._targets, **self._volume}

    def _on_data_changed(self) -> None:
        """Override in subclass to persist / signal."""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Config flow - initial setup, walks user through adding persons/devices
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class NotifyHaPlusConfigFlow(_SharedFlowMixin, config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    _targets: list[dict[str, Any]] = []
    _volume: dict[str, Any] = {}
    _selected_target_id: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is not None:
            self._targets = []
            self._volume = {
                CONF_VOLUME_NORMAL: DEFAULT_VOLUME_NORMAL,
                CONF_VOLUME_CRITICAL: DEFAULT_VOLUME_CRITICAL,
                CONF_VOLUME_AFTER: DEFAULT_VOLUME_AFTER,
                CONF_SILENT_CHANNEL: DEFAULT_SILENT_CHANNEL,
            }
            return await self.async_step_setup_menu()
        return self.async_show_form(step_id="user")

    async def async_step_setup_menu(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        return self.async_show_menu(
            step_id="setup_menu",
            menu_options=[
                "add_person",
                "add_device",
                "manage_targets",
                "volume_settings",
                "finish_setup",
            ],
        )

    async def async_step_add_person(self, user_input=None):
        return await self._do_add_person(user_input, return_step=self.async_step_setup_menu)

    async def async_step_add_device(self, user_input=None):
        return await self._do_add_device(user_input, return_step=self.async_step_setup_menu)

    async def async_step_manage_targets(self, user_input=None):
        return await self._do_manage_targets(user_input, return_step=self.async_step_setup_menu)

    async def async_step_edit_target(self, user_input=None):
        return await self._do_edit_target(user_input, return_step=self.async_step_setup_menu)

    async def async_step_volume_settings(self, user_input=None):
        return await self._do_volume_settings(user_input, return_step=self.async_step_setup_menu)

    async def async_step_finish_setup(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        return self.async_create_entry(
            title="Notify HA Plus",
            data={},
            options=self._build_options(),
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> NotifyHaPlusOptionsFlow:
        return NotifyHaPlusOptionsFlow()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Options flow - edit / add / remove after initial setup
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class NotifyHaPlusOptionsFlow(_SharedFlowMixin, config_entries.OptionsFlow):
    _targets: list[dict[str, Any]] | None = None
    _volume: dict[str, Any] | None = None
    _selected_target_id: str | None = None

    def _ensure_loaded(self) -> None:
        if self._targets is None:
            self._targets = [dict(t) for t in self.config_entry.options.get(CONF_TARGETS, [])]
        if self._volume is None:
            self._volume = {
                CONF_VOLUME_NORMAL: self.config_entry.options.get(
                    CONF_VOLUME_NORMAL, DEFAULT_VOLUME_NORMAL
                ),
                CONF_VOLUME_CRITICAL: self.config_entry.options.get(
                    CONF_VOLUME_CRITICAL, DEFAULT_VOLUME_CRITICAL
                ),
                CONF_VOLUME_AFTER: self.config_entry.options.get(
                    CONF_VOLUME_AFTER, DEFAULT_VOLUME_AFTER
                ),
                CONF_SILENT_CHANNEL: self.config_entry.options.get(
                    CONF_SILENT_CHANNEL, DEFAULT_SILENT_CHANNEL
                ),
            }

    def _on_data_changed(self) -> None:
        self.hass.config_entries.async_update_entry(
            self.config_entry, options=self._build_options()
        )
        async_dispatcher_send(self.hass, SIGNAL_OPTIONS_UPDATED)

    async def async_step_init(self, user_input=None):
        self._ensure_loaded()
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "add_person",
                "add_device",
                "manage_targets",
                "volume_settings",
            ],
        )

    async def async_step_add_person(self, user_input=None):
        return await self._do_add_person(user_input, return_step=self.async_step_init)

    async def async_step_add_device(self, user_input=None):
        return await self._do_add_device(user_input, return_step=self.async_step_init)

    async def async_step_manage_targets(self, user_input=None):
        return await self._do_manage_targets(user_input, return_step=self.async_step_init)

    async def async_step_edit_target(self, user_input=None):
        return await self._do_edit_target(user_input, return_step=self.async_step_init)

    async def async_step_volume_settings(self, user_input=None):
        return await self._do_volume_settings(user_input, return_step=self.async_step_init)
