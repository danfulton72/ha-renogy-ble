"""Tests for BLE drop-off detection and reconnect behaviour."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from tests.test_ble import _GraceDevice, _load_ble_module


class _PollableDevice(_GraceDevice):
    """Grace device with the attributes the poll path logs."""

    def __init__(self, max_failures: int = 3) -> None:
        super().__init__(max_failures=max_failures)
        self.address = "AA:BB:CC:DD:EE:FF"
        self.name = "BT-TH-12345"
        self.device_type = "controller"
        self.should_retry_connection = True


def _coordinator(ble_module, **kwargs):
    """Build a coordinator with a running hass and a connectable device."""
    coordinator = ble_module.RenogyActiveBluetoothCoordinator(
        hass=MagicMock(),
        logger=MagicMock(),
        address="AA:BB:CC:DD:EE:FF",
        scan_interval=kwargs.pop("scan_interval", 60),
        device_type=kwargs.pop("device_type", "controller"),
        **kwargs,
    )
    coordinator.hass.state = ble_module.CoreState.running
    return coordinator


def _service_info(ble_module):
    """Return service info for the coordinator's address."""
    return ble_module.BluetoothServiceInfoBleak(
        address="AA:BB:CC:DD:EE:FF",
        name="BT-TH-12345",
        rssi=-60,
    )


# --- Poll interval bookkeeping -------------------------------------------


def test_needs_poll_honors_scan_interval_between_polls() -> None:
    """A recent poll must suppress the next advertisement-driven poll.

    Regression test: the coordinator previously subtracted the callback
    argument from wall-clock now(), which always cleared the interval and made
    every advertisement trigger a connection attempt.
    """
    ble_module = _load_ble_module()
    coordinator = _coordinator(ble_module, scan_interval=60)

    with patch.object(ble_module.time, "monotonic", return_value=1_000.0):
        coordinator._mark_poll_started()

    # 10s later, well inside the 60s interval.
    with patch.object(ble_module.time, "monotonic", return_value=1_010.0):
        assert coordinator._needs_poll(_service_info(ble_module), 10.0) is False


def test_needs_poll_allows_poll_once_interval_elapses() -> None:
    """Once the interval has passed the coordinator polls again."""
    ble_module = _load_ble_module()
    coordinator = _coordinator(ble_module, scan_interval=60)

    with patch.object(ble_module.time, "monotonic", return_value=1_000.0):
        coordinator._mark_poll_started()

    with patch.object(ble_module.time, "monotonic", return_value=1_075.0):
        assert coordinator._needs_poll(_service_info(ble_module), 75.0) is True


def test_needs_poll_allows_first_poll() -> None:
    """A coordinator that has never polled must poll immediately."""
    ble_module = _load_ble_module()
    coordinator = _coordinator(ble_module)

    assert coordinator._needs_poll(_service_info(ble_module), None) is True


def test_interval_timer_defers_to_recent_bluetooth_poll() -> None:
    """The safety-net timer must not add a second poll per interval."""
    ble_module = _load_ble_module()
    coordinator = _coordinator(ble_module, scan_interval=60)
    coordinator.async_request_refresh = AsyncMock()

    with patch.object(ble_module.time, "monotonic", return_value=1_000.0):
        coordinator._mark_poll_started()

    with patch.object(ble_module.time, "monotonic", return_value=1_030.0):
        asyncio.run(coordinator._handle_refresh_interval())

    coordinator.async_request_refresh.assert_not_called()


def test_interval_timer_is_not_skipped_by_scheduler_jitter() -> None:
    """The timer must keep its cadence when it is the only poll driver.

    Regression test: poll timestamps are taken a moment after the timer fires,
    so comparing against the raw interval skipped every tick and halved the
    effective poll rate for exactly the dropped-off devices the timer exists
    to recover.
    """
    ble_module = _load_ble_module()
    coordinator = _coordinator(ble_module, scan_interval=60)
    coordinator.async_request_refresh = AsyncMock()

    lag = 0.05
    clock = {"t": lag}
    with patch.object(ble_module.time, "monotonic", lambda: clock["t"]):
        coordinator._mark_poll_started()
        for tick in range(1, 6):
            clock["t"] = tick * 60.0
            asyncio.run(coordinator._handle_refresh_interval())
            clock["t"] += lag
            coordinator._mark_poll_started()

    assert coordinator.async_request_refresh.await_count == 5


def test_interval_timer_still_suppresses_genuine_duplicates() -> None:
    """The jitter tolerance must not reopen double-polling."""
    ble_module = _load_ble_module()
    coordinator = _coordinator(ble_module, scan_interval=60)
    coordinator.async_request_refresh = AsyncMock()

    with patch.object(ble_module.time, "monotonic", return_value=1_000.0):
        coordinator._mark_poll_started()

    # Half an interval after a Bluetooth-driven poll: still clearly covered.
    with patch.object(ble_module.time, "monotonic", return_value=1_030.0):
        asyncio.run(coordinator._handle_refresh_interval())

    coordinator.async_request_refresh.assert_not_called()


def test_interval_timer_polls_when_advertisements_stop() -> None:
    """The timer must still fire when the Bluetooth path has gone quiet."""
    ble_module = _load_ble_module()
    coordinator = _coordinator(ble_module, scan_interval=60)
    coordinator.async_request_refresh = AsyncMock()

    with patch.object(ble_module.time, "monotonic", return_value=1_000.0):
        coordinator._mark_poll_started()

    with patch.object(ble_module.time, "monotonic", return_value=1_400.0):
        asyncio.run(coordinator._handle_refresh_interval())

    coordinator.async_request_refresh.assert_awaited_once()


# --- Stalled connection recovery -----------------------------------------


def test_poll_timeout_is_bounded() -> None:
    """The per-poll budget stays inside the configured floor and ceiling."""
    ble_module = _load_ble_module()

    assert _coordinator(ble_module, scan_interval=10)._poll_timeout() == 30.0
    assert _coordinator(ble_module, scan_interval=60)._poll_timeout() == 60.0
    assert _coordinator(ble_module, scan_interval=600)._poll_timeout() == 120.0


def test_stalled_read_times_out_and_releases_the_lock() -> None:
    """A hung BLE read must fail the poll rather than wedge the coordinator."""
    ble_module = _load_ble_module()
    coordinator = _coordinator(ble_module)
    device = _PollableDevice()
    coordinator.device = device
    coordinator._update_device_from_service_info = MagicMock(return_value=device)
    coordinator._poll_timeout = lambda: 0.05

    async def _hang(_device):
        await asyncio.sleep(30)

    coordinator._ble_client = MagicMock()
    coordinator._ble_client.read_device = _hang

    async def _run():
        result = await coordinator._read_device_data(_service_info(ble_module))
        # The lock must be free for the next poll attempt.
        assert coordinator._connection_lock.locked() is False
        assert coordinator._connection_busy() is False
        return result

    assert asyncio.run(_run()) is False
    assert device.failure_count == 1


def test_stalled_read_resets_the_pooled_session() -> None:
    """A timed-out read drops pooled session state before the next attempt."""
    ble_module = _load_ble_module()
    coordinator = _coordinator(ble_module)
    device = _PollableDevice()
    coordinator.device = device
    coordinator._update_device_from_service_info = MagicMock(return_value=device)
    coordinator._poll_timeout = lambda: 0.05

    async def _hang(_device):
        await asyncio.sleep(30)

    close_mock = AsyncMock()
    coordinator._ble_client = MagicMock()
    coordinator._ble_client.read_device = _hang
    coordinator._ble_client.close = close_mock

    asyncio.run(coordinator._read_device_data(_service_info(ble_module)))

    close_mock.assert_awaited_once()


def test_connection_busy_reports_a_held_lock() -> None:
    """Busy detection must consult the lock, not just the progress flag."""
    ble_module = _load_ble_module()
    coordinator = _coordinator(ble_module)

    async def _run():
        assert coordinator._connection_busy() is False
        async with coordinator._connection_lock:
            # The flag is only set inside the lock, so the flag alone would
            # still read False here and let a second caller through.
            assert coordinator._connection_in_progress is False
            assert coordinator._connection_busy() is True

    asyncio.run(_run())


# --- Stale device context -------------------------------------------------


def test_cached_device_fallback_stops_once_device_is_unavailable() -> None:
    """Persistent sessions must not retry forever against a stale BLEDevice."""
    ble_module = _load_ble_module()
    coordinator = _coordinator(ble_module)
    device = _PollableDevice()
    coordinator.device = device
    coordinator._client_transport_mode = MagicMock(
        return_value=ble_module.NonShuntConnectionMode.PERSISTENT_SESSION.value
    )

    assert coordinator._can_use_cached_device_without_service_info() is True

    for _ in range(device.max_failures):
        device.update_availability(False)

    assert coordinator._can_use_cached_device_without_service_info() is False


def test_cooldown_property_is_read_once_per_decision() -> None:
    """The cooldown check has side effects, so it must not be read twice."""
    ble_module = _load_ble_module()
    coordinator = _coordinator(ble_module)

    reads = []

    class _CooldownDevice:
        @property
        def should_retry_connection(self):
            reads.append(1)
            return False

    coordinator.device = _CooldownDevice()

    assert coordinator._should_attempt_connection() is False
    assert len(reads) == 1


# --- Sustained shunt listener --------------------------------------------


def test_shunt_reconnect_delay_backs_off_and_resets() -> None:
    """Repeated shunt reconnect failures must back off, then reset on data."""
    ble_module = _load_ble_module()
    coordinator = _coordinator(ble_module, device_type="shunt300")
    slept: list[float] = []

    async def _fake_sleep(delay):
        slept.append(delay)

    async def _run():
        with patch.object(ble_module.asyncio, "sleep", _fake_sleep):
            for _ in range(4):
                await coordinator._async_shunt_backoff_sleep()
            # A live payload resets the backoff to the base delay.
            await coordinator._async_shunt_backoff_sleep(reset=True)

    asyncio.run(_run())

    base = float(ble_module.SHUNT_RECONNECT_DELAY_SECONDS)
    assert slept[:4] == [base, base * 2, base * 4, base * 8]
    assert slept[4] == base


def test_shunt_backoff_is_capped() -> None:
    """Backoff must not grow without bound."""
    ble_module = _load_ble_module()
    coordinator = _coordinator(ble_module, device_type="shunt300")

    async def _fake_sleep(_delay):
        return None

    async def _run():
        with patch.object(ble_module.asyncio, "sleep", _fake_sleep):
            for _ in range(20):
                await coordinator._async_shunt_backoff_sleep()

    asyncio.run(_run())

    assert coordinator._shunt_reconnect_delay == float(
        ble_module.SHUNT_RECONNECT_MAX_DELAY_SECONDS
    )


def test_shunt_payload_stamps_watchdog_clock() -> None:
    """A decoded payload is what proves the sustained link is carrying data."""
    ble_module = _load_ble_module()
    coordinator = _coordinator(ble_module, device_type="shunt300")
    coordinator.device = _GraceDevice()

    payload = bytes(range(ble_module.shunt_expected_payload_length or 20))
    with (
        patch.object(
            ble_module,
            "shunt_find_valid_payload_window",
            return_value=(payload, {"shunt_voltage": 12.8}),
        ),
        patch.object(ble_module.time, "monotonic", return_value=4_242.0),
    ):
        coordinator._shunt_energy_client = None
        coordinator._process_sustained_shunt_notification(payload)

    assert coordinator._last_shunt_payload_monotonic == 4_242.0


def test_interval_timer_tolerance_is_fixed_not_percentage() -> None:
    """Long intervals must not gain a large percentage-based early window."""
    ble_module = _load_ble_module()
    coordinator = _coordinator(ble_module, scan_interval=60)
    coordinator.async_request_refresh = AsyncMock()

    with patch.object(ble_module.time, "monotonic", return_value=1_000.0):
        coordinator._mark_poll_started()

    # The previous 90% tolerance would have allowed this five seconds early.
    with patch.object(ble_module.time, "monotonic", return_value=1_055.0):
        asyncio.run(coordinator._handle_refresh_interval())
    coordinator.async_request_refresh.assert_not_called()

    # One second of scheduler jitter is intentionally tolerated.
    with patch.object(ble_module.time, "monotonic", return_value=1_059.1):
        asyncio.run(coordinator._handle_refresh_interval())
    coordinator.async_request_refresh.assert_awaited_once()


def test_riv_timeout_uses_one_poll_budget_and_resets_session() -> None:
    """A wedged RIV readback must reset transport without a second full timeout."""
    ble_module = _load_ble_module()
    coordinator = _coordinator(ble_module, device_type="inverter")
    device = _PollableDevice()
    device.device_type = "inverter"
    device.parsed_data = {"battery_voltage": 12.8}
    coordinator.device = device
    coordinator._update_device_from_service_info = MagicMock(return_value=device)
    coordinator._poll_timeout = MagicMock(return_value=0.05)

    read_result = MagicMock(success=True, error=None)
    close_mock = AsyncMock()
    coordinator._ble_client = MagicMock()
    coordinator._ble_client.read_device = AsyncMock(return_value=read_result)
    coordinator._ble_client.close = close_mock

    async def _hang_riv_readback():
        await asyncio.sleep(30)

    coordinator.async_read_riv_control_state = _hang_riv_readback

    result = asyncio.run(coordinator._read_device_data(_service_info(ble_module)))

    assert result is True
    assert coordinator._poll_timeout.call_count == 1
    close_mock.assert_awaited_once()
    assert coordinator.data["battery_voltage"] == 12.8


def test_concurrent_polls_do_not_queue_on_connection_lock() -> None:
    """A second poll must be rejected synchronously instead of waiting on the lock."""
    ble_module = _load_ble_module()
    coordinator = _coordinator(ble_module)
    device = _PollableDevice()
    device.parsed_data = {"battery_voltage": 12.8}
    coordinator.device = device
    coordinator._update_device_from_service_info = MagicMock(return_value=device)

    started = asyncio.Event()
    release = asyncio.Event()
    read_result = MagicMock(success=True, error=None)

    async def _slow_read(_device):
        started.set()
        await release.wait()
        return read_result

    coordinator._ble_client = MagicMock()
    coordinator._ble_client.read_device = AsyncMock(side_effect=_slow_read)

    async def _run():
        first = asyncio.create_task(
            coordinator._async_poll_device(_service_info(ble_module))
        )
        await started.wait()
        second = await coordinator._async_poll_device(_service_info(ble_module))
        release.set()
        first_result = await first
        return first_result, second

    first_result, second_result = asyncio.run(_run())

    assert first_result["battery_voltage"] == 12.8
    assert second_result == {}
    assert coordinator._ble_client.read_device.await_count == 1
    assert coordinator._connection_busy() is False


def test_unavailable_device_rejects_stale_service_info() -> None:
    """An unavailable device must wait for a recent advertisement before reconnect."""
    ble_module = _load_ble_module()
    coordinator = _coordinator(ble_module)
    device = _PollableDevice()
    coordinator.device = device
    for _ in range(device.max_failures):
        device.update_availability(False)

    service_info = MagicMock()
    service_info.time = 900.0
    with (
        patch.object(
            ble_module.bluetooth,
            "async_last_service_info",
            return_value=service_info,
        ),
        patch.object(ble_module.time, "monotonic", return_value=1_000.0),
    ):
        assert coordinator._service_info_for_operation() is None


def test_unavailable_device_accepts_recent_service_info() -> None:
    """A recent advertisement is sufficient to retry an unavailable device."""
    ble_module = _load_ble_module()
    coordinator = _coordinator(ble_module)
    device = _PollableDevice()
    coordinator.device = device
    for _ in range(device.max_failures):
        device.update_availability(False)

    service_info = MagicMock()
    service_info.time = 950.0
    with (
        patch.object(
            ble_module.bluetooth,
            "async_last_service_info",
            return_value=service_info,
        ),
        patch.object(ble_module.time, "monotonic", return_value=1_000.0),
    ):
        assert coordinator._service_info_for_operation() is service_info

