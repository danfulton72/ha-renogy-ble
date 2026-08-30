"""Test configuration for the Renogy BLE integration."""

import importlib
import sys

# Keep the imported test suite working while the repository moves from the old
# module path to the new Home Assistant domain. This alias exists only in tests;
# HACS installs only custom_components/renogy_ble.
renogy_ble = importlib.import_module("custom_components.renogy_ble_ble")
sys.modules.setdefault("custom_components.renogy_ble", renogy_ble)
