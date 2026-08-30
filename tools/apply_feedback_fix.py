from pathlib import Path

ble_path = Path("custom_components/renogy_ble/ble.py")
source = ble_path.read_text()

old = '''        try:
            await self._async_poll_device(service_info)
        except Exception as err:
            error_traceback = traceback.format_exc()
            self.logger.debug(
                "Error refreshing device %s: %s\\n%s",
                self.address,
                str(err),
                error_traceback,
            )
            self._record_poll_availability(False, err)

        self.async_update_listeners()
'''
new = '''        try:
            await self._async_poll_device(service_info)
        except Exception as err:
            error_traceback = traceback.format_exc()
            self.logger.debug(
                "Error refreshing device %s: %s\\n%s",
                self.address,
                str(err),
                error_traceback,
            )
            self._record_poll_availability(False, err)
            self.async_update_listeners()
'''
if old in source:
    source = source.replace(old, new, 1)

old = '''            # Update all listeners after successful data acquisition
            return dict(self.device.parsed_data)

        else:
            failed_address = (
                service_info.address if service_info is not None else self.address
            )
            self.logger.info("Failed to retrieve data from %s", failed_address)
            return self.data if isinstance(self.data, dict) else {}
'''
new = '''            # Bluetooth-driven polls call this method directly, bypassing
            # async_request_refresh(). Notify our custom entity listeners here so
            # physical inverter changes are pushed into Home Assistant.
            self.async_update_listeners()
            return dict(self.device.parsed_data)

        else:
            failed_address = (
                service_info.address if service_info is not None else self.address
            )
            self.logger.info("Failed to retrieve data from %s", failed_address)
            # Availability changes from direct Bluetooth polls also need to reach
            # entities; async_request_refresh() is not necessarily involved.
            self.async_update_listeners()
            return self.data if isinstance(self.data, dict) else {}
'''
if old not in source and "physical inverter changes are pushed" not in source:
    raise SystemExit("poll target not found")
if old in source:
    source = source.replace(old, new, 1)
ble_path.write_text(source)

test_path = Path("tests/test_ble.py")
tests = test_path.read_text()
name = "test_direct_poll_notifies_entities_after_external_control_change"
if name not in tests:
    marker = "\ndef test_sustained_shunt_refresh_does_not_poll():\n"
    addition = '''
def test_direct_poll_notifies_entities_after_external_control_change():
    """Bluetooth-driven polls must publish physical inverter state changes."""
    ble_module = _load_ble_module()
    coordinator = ble_module.RenogyActiveBluetoothCoordinator(
        hass=MagicMock(),
        logger=MagicMock(),
        address="AA:BB:CC:DD:EE:FF",
        scan_interval=30,
        device_type="inverter",
    )
    service_info = ble_module.BluetoothServiceInfoBleak(
        address="AA:BB:CC:DD:EE:FF",
        name="BT-TH-12345",
        rssi=-60,
    )
    coordinator._update_device_from_service_info(service_info)
    coordinator.device.parsed_data = {
        "model": "RIV1230PCH-23S",
        "inverter_output": 0,
    }
    coordinator.data = dict(coordinator.device.parsed_data)

    async def read_external_change(_service_info):
        coordinator.device.parsed_data["inverter_output"] = 1
        coordinator.data = dict(coordinator.device.parsed_data)
        return True

    coordinator._read_device_data = AsyncMock(side_effect=read_external_change)
    listener = MagicMock()
    coordinator.async_add_listener(listener)

    result = asyncio.run(coordinator._async_poll_device(service_info))

    assert result["inverter_output"] == 1
    listener.assert_called_once_with()


def test_manual_refresh_does_not_double_notify_after_successful_poll():
    """Manual refresh should publish one entity update, not two."""
    ble_module = _load_ble_module()
    coordinator = ble_module.RenogyActiveBluetoothCoordinator(
        hass=MagicMock(),
        logger=MagicMock(),
        address="AA:BB:CC:DD:EE:FF",
        scan_interval=30,
        device_type="controller",
    )
    service_info = ble_module.BluetoothServiceInfoBleak(
        address="AA:BB:CC:DD:EE:FF",
        name="BT-TH-12345",
        rssi=-60,
    )
    coordinator._update_device_from_service_info(service_info)
    coordinator.device.parsed_data = {"battery_voltage": 14.2}
    coordinator._ble_client.read_device = AsyncMock(
        return_value=MagicMock(success=True, error=None)
    )
    ble_module.bluetooth.async_last_service_info.return_value = service_info
    listener = MagicMock()
    coordinator.async_add_listener(listener)

    asyncio.run(coordinator.async_request_refresh())

    listener.assert_called_once_with()

'''
    if marker not in tests:
        raise SystemExit("test insertion point not found")
    test_path.write_text(tests.replace(marker, addition + marker, 1))
