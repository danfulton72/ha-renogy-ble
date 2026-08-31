"""Regression tests for sustained Smart Shunt reconnect recovery."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from tests.test_ble import _load_ble_module
from tests.test_ble_resilience import _coordinator


def test_sustained_shunt_reconnect_ignores_generic_unavailable_cooldown() -> None:
    """Fresh advertisements keep sustained shunt retries on their own backoff."""
    ble_module = _load_ble_module()
    coordinator = _coordinator(ble_module, device_type="shunt300")
    coordinator.device = MagicMock()
    coordinator.device.name = "RTMShunt300"
    coordinator._async_wait_for_shunt_startup_ready = AsyncMock()

    service_info = MagicMock()
    service_info.device = MagicMock()
    coordinator._service_info_for_operation = MagicMock(return_value=service_info)
    coordinator._update_device_from_service_info = MagicMock()
    coordinator._should_attempt_connection = MagicMock(
        side_effect=AssertionError(
            "sustained shunts must not consult the generic unavailable cooldown"
        )
    )
    coordinator._async_prepare_shunt_reconnect = AsyncMock(
        return_value=service_info.device
    )

    connect = AsyncMock(side_effect=asyncio.CancelledError())
    with patch.object(ble_module, "establish_connection", connect):
        asyncio.run(coordinator._shunt_notification_loop())

    coordinator._should_attempt_connection.assert_not_called()
    coordinator._async_prepare_shunt_reconnect.assert_awaited_once_with(
        service_info.device
    )
    connect.assert_awaited_once()


def test_shunt_startup_gate_does_not_remove_fired_one_time_listener() -> None:
    """Startup cleanup must not unsubscribe a listener HA already consumed."""
    ble_module = _load_ble_module()
    coordinator = _coordinator(ble_module, device_type="shunt300")
    coordinator._shunt_startup_gate_complete = False
    coordinator.hass.state = object()
    coordinator._has_connectable_scanner = MagicMock(return_value=True)
    coordinator._is_fresh_startup_service_info = MagicMock(return_value=True)

    service_info = MagicMock()
    remove_started = MagicMock(
        side_effect=AssertionError("one-time listener was removed twice")
    )

    def _listen_once(_event, callback):
        coordinator.hass.state = ble_module.CoreState.running
        callback(MagicMock())
        return remove_started

    coordinator.hass.bus.async_listen_once = _listen_once
    remove_bluetooth = MagicMock()

    with (
        patch.object(
            ble_module.bluetooth,
            "async_last_service_info",
            return_value=service_info,
        ),
        patch.object(
            ble_module.bluetooth,
            "async_register_callback",
            return_value=remove_bluetooth,
        ),
    ):
        asyncio.run(coordinator._async_wait_for_shunt_startup_ready())

    remove_started.assert_not_called()
    remove_bluetooth.assert_called_once()
    assert coordinator._shunt_startup_gate_complete is True
