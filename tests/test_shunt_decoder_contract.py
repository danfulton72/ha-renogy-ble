"""Contract tests that run sustained shunt decoding through the real library.

The other shunt tests stub the decoder. These tests use the installed
renogy-ble decoder so a library change that breaks reassembly fails CI.
"""

from __future__ import annotations

import importlib
import sys
from typing import Any
from unittest.mock import MagicMock, patch

from tests.test_ble import _load_ble_module

_REAL_MODULE_PREFIXES = ("bleak", "renogy_ble")


def _is_swapped_module(name: str) -> bool:
    """Return True for modules the BLE tests replace with stubs."""
    return any(
        name == prefix or name.startswith((f"{prefix}.", f"{prefix}_"))
        for prefix in _REAL_MODULE_PREFIXES
    )


def _real_shunt_module() -> Any:
    """Import the installed renogy_ble.shunt without disturbing test stubs."""
    saved = {
        name: sys.modules.pop(name)
        for name in list(sys.modules)
        if _is_swapped_module(name)
    }
    try:
        return importlib.import_module("renogy_ble.shunt")
    finally:
        for name in [name for name in sys.modules if _is_swapped_module(name)]:
            del sys.modules[name]
        sys.modules.update(saved)


def _live_frame(voltage: float, current: float, soc: float) -> bytes:
    """Build a 110-byte Smart Shunt live frame in the device's layout."""
    frame = bytearray(110)
    frame[0:4] = bytes.fromhex("42570119")
    frame[21:24] = int(current * 1000).to_bytes(3, "big", signed=True)
    frame[25:28] = int(voltage * 1000).to_bytes(3, "big")
    frame[34:36] = int(soc * 10).to_bytes(2, "big")
    return bytes(frame)


def _sustained_coordinator(ble_module: Any, shunt_module: Any) -> Any:
    """Return a sustained shunt coordinator using the real decoder."""
    hass = MagicMock()
    hass.loop.call_soon_threadsafe = lambda callback: callback()
    coordinator = ble_module.RenogyActiveBluetoothCoordinator(
        hass=hass,
        logger=MagicMock(),
        address="AA:BB:CC:DD:EE:FF",
        scan_interval=30,
        device_type="shunt300",
        shunt_connection_mode="sustained",
    )
    coordinator.device = MagicMock(parsed_data={})
    coordinator._shunt_decoder = shunt_module.ShuntNotificationDecoder()
    return coordinator


def test_fragmented_frame_is_reassembled_and_published() -> None:
    """A frame split across two notifications produces one reading."""
    shunt_module = _real_shunt_module()
    ble_module = _load_ble_module()
    coordinator = _sustained_coordinator(ble_module, shunt_module)
    frame = _live_frame(voltage=13.2, current=-4.5, soc=85.0)

    with patch.object(ble_module.time, "monotonic", return_value=100.0):
        assert coordinator._process_sustained_shunt_notification(frame[:55]) is False
        assert coordinator._process_sustained_shunt_notification(frame[55:]) is True

    assert coordinator.data["shunt_voltage"] == 13.2
    assert coordinator.data["shunt_current"] == -4.5
    assert coordinator.data["shunt_soc"] == 85.0
    assert coordinator.data["raw_payload"] == frame.hex()
    assert len(coordinator.data["raw_words"]) == 55
    assert coordinator._last_shunt_payload_monotonic == 100.0


def test_whole_frame_in_one_notification_is_published() -> None:
    """A frame delivered in a single notification still decodes."""
    shunt_module = _real_shunt_module()
    ble_module = _load_ble_module()
    coordinator = _sustained_coordinator(ble_module, shunt_module)

    with patch.object(ble_module.time, "monotonic", return_value=100.0):
        assert coordinator._process_sustained_shunt_notification(
            _live_frame(voltage=12.8, current=2.0, soc=60.0)
        )

    assert coordinator.data["shunt_voltage"] == 12.8
    assert coordinator.data["energy_charged_total"] == 0.0


def test_fragment_without_completion_does_not_feed_watchdog() -> None:
    """Partial bytes alone must not count as live data."""
    shunt_module = _real_shunt_module()
    ble_module = _load_ble_module()
    coordinator = _sustained_coordinator(ble_module, shunt_module)
    coordinator._last_shunt_payload_monotonic = None

    frame = _live_frame(voltage=13.2, current=1.0, soc=50.0)
    assert coordinator._process_sustained_shunt_notification(frame[:55]) is False

    assert coordinator._last_shunt_payload_monotonic is None
    assert coordinator.data is None or "shunt_voltage" not in coordinator.data


def test_sustained_loop_stops_when_decoder_is_unavailable() -> None:
    """Missing decoder support fails visibly instead of looping without data."""
    import asyncio

    ble_module = _load_ble_module()
    hass = MagicMock()
    hass.loop.call_soon_threadsafe = lambda callback: callback()
    coordinator = ble_module.RenogyActiveBluetoothCoordinator(
        hass=hass,
        logger=MagicMock(),
        address="AA:BB:CC:DD:EE:FF",
        scan_interval=30,
        device_type="shunt300",
        shunt_connection_mode="sustained",
    )
    coordinator._shunt_decoder = None

    # Bound the run so a regression fails instead of looping forever.
    asyncio.run(asyncio.wait_for(coordinator._shunt_notification_loop(), timeout=5))

    coordinator.logger.error.assert_called_once()
    assert coordinator.last_update_success is False
