"""Renogy BLE integration for Home Assistant."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Protocol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import async_get as async_get_device_registry

from .const import (
    CONF_COMMUNICATION_HUB_ENABLED,
    CONF_DEVICE_TYPE,
    CONF_MAX_FAILURES,
    CONF_NON_SHUNT_CONNECTION_MODE,
    CONF_SCAN_INTERVAL,
    CONF_SHUNT_CONNECTION_MODE,
    CONF_UNAVAILABLE_RETRY_INTERVAL,
    DEFAULT_COMMUNICATION_HUB_ENABLED,
    DEFAULT_DEVICE_TYPE,
    DEFAULT_MAX_FAILURES,
    DEFAULT_NON_SHUNT_CONNECTION_MODE,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SHUNT_CONNECTION_MODE,
    DEFAULT_UNAVAILABLE_RETRY_INTERVAL,
    DOMAIN,
    LOGGER,
    DeviceType,
)
from .device_name import detect_device_type_from_model, has_real_device_name

if TYPE_CHECKING:
    from .ble import RenogyActiveBluetoothCoordinator, RenogyBLEDevice

PLATFORMS = [Platform.SENSOR, Platform.NUMBER, Platform.SELECT, Platform.SWITCH]


class _CoordinatorShutdownProtocol(Protocol):
    """Coordinator interface needed for deferred shutdown."""

    async def async_shutdown(self) -> None:
        """Release coordinator resources."""


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Renogy BLE from a config entry."""
    from .ble import RenogyActiveBluetoothCoordinator

    LOGGER.info("Setting up Renogy BLE integration with entry %s", entry.entry_id)

    scan_interval = _resolve_setting(entry, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    max_failures = _resolve_setting(entry, CONF_MAX_FAILURES, DEFAULT_MAX_FAILURES)
    unavailable_retry_interval = _resolve_setting(
        entry, CONF_UNAVAILABLE_RETRY_INTERVAL, DEFAULT_UNAVAILABLE_RETRY_INTERVAL
    )
    device_address = entry.data.get(CONF_ADDRESS)
    device_type = entry.data.get(CONF_DEVICE_TYPE, DEFAULT_DEVICE_TYPE)
    shunt_connection_mode = _get_shunt_connection_mode(entry)
    non_shunt_connection_mode = _get_non_shunt_connection_mode(entry)
    communication_hub_enabled = _get_communication_hub_enabled(entry)

    if not device_address:
        LOGGER.error("No device address provided in config entry")
        return False

    LOGGER.info(
        "Configuring Renogy BLE device %s as %s with scan interval %ss "
        "(shunt mode: %s, non-shunt mode: %s, communication hub: %s)",
        device_address,
        device_type,
        scan_interval,
        shunt_connection_mode,
        non_shunt_connection_mode,
        "enabled" if communication_hub_enabled else "disabled",
    )

    async def device_data_callback(device: RenogyBLEDevice) -> None:
        """Forward coordinator device updates to the integration handler."""
        await _handle_device_update(hass, entry, device)

    if communication_hub_enabled:
        from .hub_coordinator import RenogyHubBluetoothCoordinator

        coordinator = RenogyHubBluetoothCoordinator(
            hass=hass,
            logger=LOGGER,
            address=device_address,
            scan_interval=scan_interval,
            device_type=device_type,
            shunt_connection_mode=shunt_connection_mode,
            non_shunt_connection_mode=non_shunt_connection_mode,
            max_failures=max_failures,
            unavailable_retry_interval=unavailable_retry_interval,
            device_data_callback=device_data_callback,
            communication_hub_enabled=True,
        )
    else:
        coordinator = RenogyActiveBluetoothCoordinator(
            hass=hass,
            logger=LOGGER,
            address=device_address,
            scan_interval=scan_interval,
            device_type=device_type,
            shunt_connection_mode=shunt_connection_mode,
            non_shunt_connection_mode=non_shunt_connection_mode,
            max_failures=max_failures,
            unavailable_retry_interval=unavailable_retry_interval,
            device_data_callback=device_data_callback,
        )

    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "devices": [],
        "initialized_devices": set(),
    }

    # Perform a synchronous first read before async_start(). async_start() itself
    # schedules a refresh, so starting first can race the awaited refresh and cause
    # setup to continue before the model has arrived.
    LOGGER.info("Requesting initial refresh for Renogy BLE device %s", device_address)
    try:
        await coordinator.async_request_refresh()
    except Exception as e:
        LOGGER.warning("Initial refresh failed for %s: %s", device_address, e)

    # BT-TH is a generic radio module used by several product families. Once the
    # product model is known, prefer that model-derived type and rebuild the BLE
    # client so inverter writes use the inverter Modbus device ID (0x20).
    await _async_reconcile_model_device_type(coordinator)

    LOGGER.info("Starting coordinator for Renogy BLE device %s", device_address)
    try:
        stop_func = coordinator.async_start()
        entry.async_on_unload(stop_func)
    except Exception as e:
        LOGGER.error("Error starting coordinator for %s: %s", device_address, e)

    LOGGER.info("Setting up platforms for Renogy BLE device %s", device_address)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def _async_reconcile_model_device_type(
    coordinator: RenogyActiveBluetoothCoordinator,
) -> None:
    """Resolve a generic BLE entry to the product type reported by its model."""
    if not isinstance(coordinator.data, dict):
        return

    model = coordinator.data.get("model")
    detected_type = detect_device_type_from_model(model)
    if detected_type is None or detected_type == coordinator.device_type:
        return

    previous_type = coordinator.device_type
    LOGGER.info(
        "Resolved Renogy device %s from configured type '%s' to '%s' using model %s",
        coordinator.address,
        previous_type,
        detected_type,
        model,
    )

    old_client = coordinator._ble_client
    close_client = getattr(old_client, "close", None)
    if callable(close_client):
        try:
            await close_client()
        except Exception:
            LOGGER.debug(
                "Unable to close previous BLE client while changing %s to %s",
                coordinator.address,
                detected_type,
                exc_info=True,
            )

    coordinator.device_type = detected_type
    if coordinator.device is not None:
        coordinator.device.device_type = detected_type
    coordinator._ble_client = coordinator._build_ble_client_for_type(detected_type)


def _resolve_setting(entry: ConfigEntry, key: str, default: int) -> int:
    """Resolve a setting from options, then data, then the given default."""
    return entry.options.get(key, entry.data.get(key, default))


def _get_shunt_connection_mode(entry: ConfigEntry) -> str:
    """Return the configured Smart Shunt connection mode for an entry."""
    device_type = entry.data.get(CONF_DEVICE_TYPE, DEFAULT_DEVICE_TYPE)
    if device_type != DeviceType.SHUNT300.value:
        return DEFAULT_SHUNT_CONNECTION_MODE

    return entry.options.get(
        CONF_SHUNT_CONNECTION_MODE,
        DEFAULT_SHUNT_CONNECTION_MODE,
    )


def _get_non_shunt_connection_mode(entry: ConfigEntry) -> str:
    """Return the configured non-shunt connection mode for an entry."""
    device_type = entry.data.get(CONF_DEVICE_TYPE, DEFAULT_DEVICE_TYPE)
    if device_type == DeviceType.SHUNT300.value:
        return DEFAULT_NON_SHUNT_CONNECTION_MODE

    return entry.options.get(
        CONF_NON_SHUNT_CONNECTION_MODE,
        DEFAULT_NON_SHUNT_CONNECTION_MODE,
    )


def _get_communication_hub_enabled(entry: ConfigEntry) -> bool:
    """Return whether Communication Hub battery polling is enabled."""
    device_type = entry.data.get(CONF_DEVICE_TYPE, DEFAULT_DEVICE_TYPE)
    if device_type == DeviceType.SHUNT300.value:
        return False

    return bool(
        entry.options.get(
            CONF_COMMUNICATION_HUB_ENABLED,
            DEFAULT_COMMUNICATION_HUB_ENABLED,
        )
    )


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def _handle_device_update(
    hass: HomeAssistant, entry: ConfigEntry, device: RenogyBLEDevice
) -> None:
    """Handle device update callback."""
    LOGGER.debug("Device update for %s (%s)", device.name, device.address)

    if entry.entry_id in hass.data[DOMAIN]:
        entry_data = hass.data[DOMAIN][entry.entry_id]
        devices_list = entry_data.get("devices", [])

        device_addresses = [d.address for d in devices_list]
        if device.address not in device_addresses:
            LOGGER.debug("Adding device %s to registry", device.name)
            devices_list.append(device)

            if device.parsed_data:
                LOGGER.debug("Device data: %s", device.parsed_data)
            else:
                LOGGER.warning("No parsed data for device %s", device.name)

        if has_real_device_name(device.name):
            await update_device_registry(hass, entry, device)


async def update_device_registry(
    hass: HomeAssistant, entry: ConfigEntry, device: RenogyBLEDevice
) -> None:
    """Update device in registry."""
    try:
        device_registry = async_get_device_registry(hass)
        model = (
            device.parsed_data.get("model", device.device_type.capitalize())
            if device.parsed_data
            else device.device_type.capitalize()
        )

        device_entry = device_registry.async_get_device({(DOMAIN, device.address)})

        if device_entry:
            LOGGER.debug(
                "Updating device registry entry with real name: %s", device.name
            )
            device_registry.async_update_device(
                device_entry.id, name=device.name, model=model
            )
        else:
            LOGGER.debug("Device %s not found in registry for update", device.address)
    except Exception as e:
        LOGGER.error("Error updating device in registry: %s", e)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    LOGGER.debug("Unloading Renogy BLE integration for %s", entry.entry_id)

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok and entry.entry_id in hass.data[DOMAIN]:
        coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
        coordinator.async_stop()
        hass.async_create_task(_async_shutdown_coordinator(coordinator, entry.entry_id))
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def _async_shutdown_coordinator(
    coordinator: _CoordinatorShutdownProtocol, entry_id: str
) -> None:
    """Attempt coordinator shutdown without blocking entry unload."""
    try:
        await asyncio.wait_for(coordinator.async_shutdown(), timeout=5)
    except TimeoutError:
        LOGGER.warning(
            "Timed out shutting down Renogy BLE coordinator for %s; "
            "persistent session cleanup will continue in the background",
            entry_id,
        )
    except Exception:
        LOGGER.exception(
            "Error shutting down Renogy BLE coordinator for %s",
            entry_id,
        )