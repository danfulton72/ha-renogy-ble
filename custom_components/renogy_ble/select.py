"""Support for Renogy BLE select entities."""

from __future__ import annotations

from typing import Optional, cast

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .availability import is_entity_available
from .ble import RenogyActiveBluetoothCoordinator, RenogyBLEDevice
from .const import (
    ATTR_MANUFACTURER,
    CONF_DEVICE_TYPE,
    DCC_BATTERY_TYPE_VALUES,
    DCC_BATTERY_TYPES,
    DCC_MAX_CURRENT_OPTIONS,
    DCC_MAX_CURRENT_TO_DEVICE,
    DEFAULT_DEVICE_TYPE,
    DOMAIN,
    LOGGER,
    RIV_INVERTER_MODEL_PREFIX,
    DCCRegister,
    DeviceType,
    InverterRegister,
)

BATTERY_TYPE_DISPLAY_NAMES = {
    "custom": "Custom",
    "open": "Open (Flooded)",
    "sealed": "Sealed (AGM)",
    "gel": "Gel",
    "lithium": "Lithium",
}

MAX_CURRENT_OPTIONS = [f"{amp}A" for amp in DCC_MAX_CURRENT_OPTIONS]
MAX_CURRENT_DISPLAY_TO_AMPS = {f"{amp}A": amp for amp in DCC_MAX_CURRENT_OPTIONS}

DCC_SELECT_ENTITIES = (
    SelectEntityDescription(
        key="battery_type",
        name="Battery Type",
        entity_category=EntityCategory.CONFIG,
    ),
    SelectEntityDescription(
        key="max_charging_current",
        name="Max Charging Current",
        entity_category=EntityCategory.CONFIG,
    ),
)


def _coordinator_model(coordinator: RenogyActiveBluetoothCoordinator) -> str:
    """Return the latest model reported by the coordinator."""
    if coordinator.device and coordinator.device.parsed_data:
        return str(coordinator.device.parsed_data.get("model", ""))
    if isinstance(coordinator.data, dict):
        return str(coordinator.data.get("model", ""))
    return ""


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Renogy BLE select entities."""
    LOGGER.debug(
        "Setting up Renogy BLE select entities for entry: %s", config_entry.entry_id
    )

    renogy_data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = renogy_data["coordinator"]
    configured_device_type = config_entry.data.get(
        CONF_DEVICE_TYPE, DEFAULT_DEVICE_TYPE
    )
    device_type = getattr(coordinator, "device_type", configured_device_type)
    if not isinstance(device_type, str):
        device_type = configured_device_type

    if device_type == DeviceType.INVERTER.value:
        if _coordinator_model(coordinator).upper().startswith(RIV_INVERTER_MODEL_PREFIX):
            async_add_entities(
                [RenogyOutputPrioritySelect(coordinator, coordinator.device)]
            )
        return

    if device_type != DeviceType.DCC.value:
        LOGGER.debug(
            "Skipping select entities for non-DCC device type: %s", device_type
        )
        return

    entities = []
    device = coordinator.device
    for description in DCC_SELECT_ENTITIES:
        if description.key == "battery_type":
            entity = RenogyBatteryTypeSelect(
                coordinator=coordinator,
                device=device,
                description=description,
                device_type=device_type,
            )
        elif description.key == "max_charging_current":
            entity = RenogyMaxCurrentSelect(
                coordinator=coordinator,
                device=device,
                description=description,
                device_type=device_type,
            )
        else:
            continue
        entities.append(entity)

    if entities:
        async_add_entities(entities)


class RenogyBatteryTypeSelect(SelectEntity):
    """Representation of a Renogy battery type select entity."""

    entity_description: SelectEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: RenogyActiveBluetoothCoordinator,
        device: Optional[RenogyBLEDevice],
        description: SelectEntityDescription,
        device_type: str = DEFAULT_DEVICE_TYPE,
    ) -> None:
        self.coordinator = coordinator
        self._device = device
        self.entity_description = description
        self._attr_options = list(BATTERY_TYPE_DISPLAY_NAMES.values())
        self._attr_current_option = None

        if device:
            self._attr_unique_id = f"{device.address}_{description.key}"
            self._attr_name = cast("str | None", description.name)
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, device.address)},
                name=device.name,
                manufacturer=ATTR_MANUFACTURER,
                model=f"Renogy {device_type.upper()}",
            )
        else:
            self._attr_unique_id = f"{coordinator.address}_{description.key}"
            self._attr_name = cast("str | None", description.name)
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, coordinator.address)},
                name=f"Renogy {device_type.upper()}",
                manufacturer=ATTR_MANUFACTURER,
            )

    @property
    def suggested_object_id(self) -> str | None:
        if self._device is None:
            return f"Renogy {self._attr_name}"
        return super().suggested_object_id

    @property
    def available(self) -> bool:
        return is_entity_available(self.coordinator, self._device)

    @property
    def current_option(self) -> str | None:
        if self._attr_current_option is not None:
            return self._attr_current_option

        data = None
        if self._device and self._device.parsed_data:
            data = self._device.parsed_data
        elif self.coordinator.data:
            data = self.coordinator.data
        if not data:
            return None

        battery_type = data.get("battery_type")
        if isinstance(battery_type, str):
            display_name = BATTERY_TYPE_DISPLAY_NAMES.get(battery_type.lower())
            if display_name:
                self._attr_current_option = display_name
                return display_name
        if isinstance(battery_type, int):
            type_key = DCC_BATTERY_TYPES.get(battery_type)
            if type_key:
                display_name = BATTERY_TYPE_DISPLAY_NAMES.get(type_key)
                if display_name:
                    self._attr_current_option = display_name
                    return display_name
        return None

    async def async_select_option(self, option: str) -> None:
        type_key = next(
            (key for key, display in BATTERY_TYPE_DISPLAY_NAMES.items() if display == option),
            None,
        )
        if type_key is None:
            LOGGER.error("Unknown battery type option: %s", option)
            return
        device_value = DCC_BATTERY_TYPE_VALUES.get(type_key)
        if device_value is None:
            LOGGER.error("No device value for battery type: %s", type_key)
            return
        if await self.coordinator.async_write_register(
            DCCRegister.BATTERY_TYPE, device_value
        ):
            self._attr_current_option = option
            self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )

    def _handle_coordinator_update(self) -> None:
        self._attr_current_option = None
        if not self._device and self.coordinator.device:
            self._device = self.coordinator.device
        self.async_write_ha_state()


class RenogyMaxCurrentSelect(SelectEntity):
    """Representation of a Renogy max charging current select entity."""

    entity_description: SelectEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: RenogyActiveBluetoothCoordinator,
        device: Optional[RenogyBLEDevice],
        description: SelectEntityDescription,
        device_type: str = DEFAULT_DEVICE_TYPE,
    ) -> None:
        self.coordinator = coordinator
        self._device = device
        self.entity_description = description
        self._attr_options = MAX_CURRENT_OPTIONS
        self._attr_current_option = None

        if device:
            self._attr_unique_id = f"{device.address}_{description.key}"
            self._attr_name = cast("str | None", description.name)
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, device.address)},
                name=device.name,
                manufacturer=ATTR_MANUFACTURER,
                model=f"Renogy {device_type.upper()}",
            )
        else:
            self._attr_unique_id = f"{coordinator.address}_{description.key}"
            self._attr_name = cast("str | None", description.name)
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, coordinator.address)},
                name=f"Renogy {device_type.upper()}",
                manufacturer=ATTR_MANUFACTURER,
            )

    @property
    def suggested_object_id(self) -> str | None:
        if self._device is None:
            return f"Renogy {self._attr_name}"
        return super().suggested_object_id

    @property
    def available(self) -> bool:
        return is_entity_available(self.coordinator, self._device)

    @property
    def current_option(self) -> str | None:
        if self._attr_current_option is not None:
            return self._attr_current_option
        data = None
        if self._device and self._device.parsed_data:
            data = self._device.parsed_data
        elif self.coordinator.data:
            data = self.coordinator.data
        if not data:
            return None
        current_amps = data.get("max_charging_current")
        if current_amps is None:
            return None
        try:
            current_int = int(round(float(current_amps)))
            if current_int in DCC_MAX_CURRENT_OPTIONS:
                display = f"{current_int}A"
                self._attr_current_option = display
                return display
        except (ValueError, TypeError):
            pass
        return None

    async def async_select_option(self, option: str) -> None:
        amp_value = MAX_CURRENT_DISPLAY_TO_AMPS.get(option)
        if amp_value is None:
            LOGGER.error("Unknown max current option: %s", option)
            return
        device_value = DCC_MAX_CURRENT_TO_DEVICE.get(amp_value)
        if device_value is None:
            LOGGER.error("No device value for current: %sA", amp_value)
            return
        if await self.coordinator.async_write_register(
            DCCRegister.MAX_CHARGING_CURRENT, device_value
        ):
            self._attr_current_option = option
            self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )

    def _handle_coordinator_update(self) -> None:
        self._attr_current_option = None
        if not self._device and self.coordinator.device:
            self._device = self.coordinator.device
        self.async_write_ha_state()


class RenogyOutputPrioritySelect(SelectEntity):
    """RIV inverter output-priority setting."""

    _attr_has_entity_name = True
    _attr_name = "Output Priority"
    _attr_options = ["Grid First", "Battery First"]
    _VALUES = {"Grid First": 1, "Battery First": 2}

    def __init__(
        self,
        coordinator: RenogyActiveBluetoothCoordinator,
        device: Optional[RenogyBLEDevice],
    ) -> None:
        self.coordinator = coordinator
        self._device = device
        self._attr_current_option = None
        address = device.address if device else coordinator.address
        self._attr_unique_id = f"{address}_inverter_output_priority"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, address)},
            name=device.name if device else "Renogy RIV Inverter",
            manufacturer=ATTR_MANUFACTURER,
            model=_coordinator_model(coordinator) or "Renogy RIV Inverter",
        )

    @property
    def available(self) -> bool:
        return is_entity_available(self.coordinator, self._device)

    @property
    def current_option(self) -> str | None:
        return self._attr_current_option

    async def async_select_option(self, option: str) -> None:
        value = self._VALUES[option]
        if await self.coordinator.async_write_register(
            InverterRegister.OUTPUT_PRIORITY, value
        ):
            self._attr_current_option = option
            self.async_write_ha_state()