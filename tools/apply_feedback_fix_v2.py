from pathlib import Path

ble_path = Path("custom_components/renogy_ble/ble.py")
source = ble_path.read_text()

old = '''        # Add connection lock to prevent multiple concurrent connections
        self._connection_lock = asyncio.Lock()
        self._connection_in_progress = False
'''
new = '''        # Add connection lock to prevent multiple concurrent connections
        self._connection_lock = asyncio.Lock()
        self._connection_in_progress = False
        # Manual refreshes notify listeners themselves; direct Bluetooth polls do not.
        self._manual_refresh_in_progress = False
'''
if old not in source and "_manual_refresh_in_progress = False" not in source:
    raise SystemExit("init target not found")
if old in source:
    source = source.replace(old, new, 1)

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
            self._manual_refresh_in_progress = True
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
        finally:
            self._manual_refresh_in_progress = False

        self.async_update_listeners()
'''
if old not in source:
    raise SystemExit("refresh target not found")
source = source.replace(old, new, 1)

source = source.replace(
    '''            self.async_update_listeners()
            return dict(self.device.parsed_data)
''',
    '''            if not self._manual_refresh_in_progress:
                self.async_update_listeners()
            return dict(self.device.parsed_data)
''',
    1,
)
source = source.replace(
    '''            self.async_update_listeners()
            return self.data if isinstance(self.data, dict) else {}
''',
    '''            if not self._manual_refresh_in_progress:
                self.async_update_listeners()
            return self.data if isinstance(self.data, dict) else {}
''',
    1,
)

ble_path.write_text(source)
