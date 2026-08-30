"""Support for Renogy BLE writable number entities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, cast

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfElectricCurrent, UnitOfElectricPotential, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .availability import is_entity_available
from .ble import RenogyActiveBluetoothCoordinator, RenogyBLEDevice
from .const import (
    ATTR_MANUFACTURER,
    CONF_DEVICE_NAME,
    CONF_DEVICE_TYPE,
    DEFAULT_DEVICE_TYPE,
    DOMAIN,
    LOGGER,
    RENOGY_REGO_INVERTER_PREFIX,
    RIV_INVERTER_MODEL_PREFIX,
    DCCRegister,
    DeviceType,
    InverterRegister,
)


@dataclass(frozen=True)
class RenogyNumberEntityDescription(NumberEntityDescription):
    """Describe a writable Renogy number entity."""

    register: int = 0
    scale: float = 1.0


def _voltage_description(
    key: str,
    name: str,
    register: int,
    minimum: float = 7.0,
    maximum: float = 17.0,
) -> RenogyNumberEntityDescription:
    return RenogyNumberEntityDescription(
        key=key,
        name=name,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=NumberDeviceClass.VOLTAGE,
        native_min_value=minimum,
        native_max_value=maximum,
        native_step=0.1,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        register=register,
        scale=10.0,
    )


DCC_VOLTAGE_NUMBERS: tuple[RenogyNumberEntityDescription, ...] = (
    _voltage_description("overvoltage_threshold", "Overvoltage Threshold", DCCRegister.OVERVOLTAGE_THRESHOLD),
    _voltage_description("charging_limit_voltage", "Charging Limit Voltage", DCCRegister.CHARGING_LIMIT_VOLTAGE),
    _voltage_description("equalization_voltage", "Equalization Voltage", DCCRegister.EQUALIZATION_VOLTAGE),
    _voltage_description("boost_voltage", "Boost Voltage", DCCRegister.BOOST_VOLTAGE),
    _voltage_description("float_voltage", "Float Voltage", DCCRegister.FLOAT_VOLTAGE),
    _voltage_description("boost_return_voltage", "Boost Return Voltage", DCCRegister.BOOST_RETURN_VOLTAGE),
    _voltage_description("overdischarge_return_voltage", "Overdischarge Return Voltage", DCCRegister.OVERDISCHARGE_RETURN_VOLTAGE),
    _voltage_description("undervoltage_warning", "Undervoltage Warning", DCCRegister.UNDERVOLTAGE_WARNING),
    _voltage_description("overdischarge_voltage", "Overdischarge Voltage", DCCRegister.OVERDISCHARGE_VOLTAGE),
    _voltage_description("discharge_limit_voltage", "Discharge Limit Voltage", DCCRegister.DISCHARGE_LIMIT_VOLTAGE),
    _voltage_description("reverse_charging_voltage", "Reverse Charging Voltage", DCCRegister.REVERSE_CHARGING_VOLTAGE, 11.0, 15.0),
)

DCC_TIME_NUMBERS: tuple[RenogyNumberEntityDescription, ...] = (
    RenogyNumberEntityDescription(
        key="overdischarge_delay",
        name="Overdischarge Delay",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        native_min_value=0,
        native_max_value=120,
        native_step=1,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        register=DCCRegister.OVERDISCHARGE_DELAY,
    ),
    RenogyNumberEntityDescription(
        key="equalization_time",
        name="Equalization Time",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        native_min_value=0,
        native_max_value=300,
        native_step=1,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        register=DCCRegister.EQUALIZATION_TIME,
    ),
    RenogyNumberEntityDescription(
        key="boost_time",
        name="Boost Time",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        native_min_value=10,
        native_max_value=300,
        native_step=1,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        register=DCCRegister.BOOST_TIME,
    ),
    RenogyNumberEntityDescription(
        key="equalization_interval",
        name="Equalization Interval",
        native_unit_of_measurement=UnitOfTime.DAYS,
        native_min_value=0,
        native_max_value=255,
        native_step=1,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        register=DCCRegister.EQUALIZATION_INTERVAL,
    ),
)

DCC_OTHER_NUMBERS: tuple[RenogyNumberEntityDescription, ...] = (
    RenogyNumberEntityDescription(
        key="temperature_compensation",
        name="Temperature Compensation",
        native_unit_of_measurement="mV/C/2V",
        native_min_value=0,
        native_max_value=5,
        native_step=1,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        register=DCCRegister.TEMPERATURE_COMPENSATION,
    ),
    RenogyNumberEntityDescription(
        key="solar_cutoff_current",
        name="Solar Cutoff Current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=NumberDeviceClass.CURRENT,
        native_min_value=0,
        native_max_value=10,
        native_step=1,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        register=DCCRegister.SOLAR_CUTOFF_CURRENT,
        scale=100.0,
    ),
)

DCC_ALL_NUMBERS = DCC_VOLTAGE_NUMBERS + DCC_TIME_NUMBERS + DCC_OTHER_NUMBERS

INVERTER_ALL_NUMBERS: tuple[RenogyNumberEntityDescription, ...] = (
    RenogyNumberEntityDescription(
        key="inverter_ac_input_current_limit",
        name="AC Input Current Limit",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=NumberDeviceClass.CURRENT,
        native_min_value=1.0,
        native_max_value=50.0,
        native_step=1.0,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        register=InverterRegister.AC_INPUT_CURRENT_LIMIT,
        scale=10.0,
    ),
    RenogyNumberEntityDescription(
        key="inverter_charge_current",
        name="Charge Current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=NumberDeviceClass.CURRENT,
        native_min_value=5.0,
        native_max_value=150.0,
        native_step=5.0,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        register=InverterRegister.CHARGE_CURRENT,
        scale=10.0,
    ),
    _voltage_description("inverter_low_voltage_warn", "Low Voltage Warning", InverterRegister.LOW_VOLTAGE_WARN, 9.0, 15.5),
    _voltage_description("inverter_over_voltage", "Battery Over Voltage", InverterRegister.BATTERY_OVER_VOLTAGE, 9.0, 16.0),
)

# RIV1230PCH-23S controls confirmed from Renogy app BLE traffic.
RIV_INVERTER_NUMBERS: tuple[RenogyNumberEntityDescription, ...] = (
    RenogyNumberEntityDescription(
        key="inverter_charge_current",
        name="Charge Current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=NumberDeviceClass.CURRENT,
        native_min_value=30.0,
        native_max_value=120.0,
        native_step=5.0,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        register=InverterRegister.CHARGE_CURRENT,
        scale=10.0,
    ),
    _voltage_description("inverter_equalization_voltage", "Equalization Voltage", InverterRegister.EQUALIZATION_VOLTAGE, 9.0, 15.5),
    _voltage_description("inverter_boost_voltage", "Boost Voltage", InverterRegister.BOOST_VOLTAGE, 9.0, 15.5),
    _voltage_description("inverter_float_voltage", "Float Voltage", InverterRegister.FLOAT_VOLTAGE, 9.0, 15.5),
    _voltage_description("inverter_low_voltage_warn", "Low Voltage Warning", InverterRegister.LOW_VOLTAGE_WARN, 9.0, 15.5),
    _voltage_description("inverter_overdischarge_shutdown", "Overdischarge Shutdown", InverterRegister.OVERDISCHARGE_SHUTDOWN, 9.0, 15.5),
    _voltage_description("inverter_over_voltage", "Over Voltage Protection", InverterRegister.BATTERY_OVER_VOLTAGE, 9.0, 16.0),
    _voltage_description("inverter_overvoltage_recovery", "Overvoltage Recovery", InverterRegister.OVERVOLTAGE_RECOVERY, 9.0, 15.5),
    _voltage_description("inverter_undervoltage_recovery", "Undervoltage Recovery", InverterRegister.UNDERVOLTAGE_RECOVERY, 9.0, 16.0),
)


def _coordinator_model(coordinator: RenogyActiveBluetoothCoordinator) -> str:
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
    """Set up the Renogy BLE number entities."""
    renogy_data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = renogy_data["coordinator"]
    configured_device_type = config_entry.data.get(
        CONF_DEVICE_TYPE, DEFAULT_DEVICE_TYPE
    )
    device_type = getattr(coordinator, "device_type", configured_device_type)
    if not isinstance(device_type, str):
        device_type = configured_device_type
    model = _coordinator_model(coordinator)

    if device_type == DeviceType.DCC.value:
        descriptions = DCC_ALL_NUMBERS
    elif device_type == DeviceType.INVERTER.value and model.upper().startswith(
        RIV_INVERTER_MODEL_PREFIX
    ):
        descriptions = RIV_INVERTER_NUMBERS
    elif device_type == DeviceType.INVERTER.value and str(
        config_entry.data.get(CONF_DEVICE_NAME, "")
    ).startswith(RENOGY_REGO_INVERTER_PREFIX):
        descriptions = INVERTER_ALL_NUMBERS
    else:
        LOGGER.debug("No number entities for device type: %s", device_type)
        return

    device = coordinator.device
    async_add_entities(
        [
            RenogyNumberEntity(
                coordinator=coordinator,
                device=device,
                description=description,
                device_type=device_type,
            )
            for description in descriptions
        ]
    )


class RenogyNumberEntity(NumberEntity):
    """Representation of a Renogy BLE number entity."""

    entity_description: RenogyNumberEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: RenogyActiveBluetoothCoordinator,
        device: Optional[RenogyBLEDevice],
        description: RenogyNumberEntityDescription,
        device_type: str = DEFAULT_DEVICE_TYPE,
    ) -> None:
        self.coordinator = coordinator
        self._device = device
        self.entity_description = description
        self._attr_native_value = None

        if device:
            self._attr_unique_id = f"{device.address}_{description.key}"
            self._attr_name = cast("str | None", description.name)
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, device.address)},
                name=device.name,
                manufacturer=ATTR_MANUFACTURER,
                model=_coordinator_model(coordinator) or f"Renogy {device_type.upper()}",
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
    def native_value(self) -> float | None:
        if self._attr_native_value is not None:
            return self._attr_native_value
        data = None
        if self._device and self._device.parsed_data:
            data = self._device.parsed_data
        elif self.coordinator.data:
            data = self.coordinator.data
        if not data:
            return None
        value = data.get(self.entity_description.key)
        if value is not None:
            self._attr_native_value = float(value)
        return self._attr_native_value

    async def async_set_native_value(self, value: float) -> None:
        device_value = int(value * self.entity_description.scale)
        success = await self.coordinator.async_write_register(
            self.entity_description.register, device_value
        )
        if success:
            self._attr_native_value = value
            self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )

    def _handle_coordinator_update(self) -> None:
        self._attr_native_value = None
        if not self._device and self.coordinator.device:
            self._device = self.coordinator.device
        self.async_write_ha_state()