"""Regression tests for RIV inverter controls."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONST_SOURCE = (ROOT / "custom_components" / "renogy_ble" / "const.py").read_text()
NUMBER_SOURCE = (ROOT / "custom_components" / "renogy_ble" / "number.py").read_text()
SELECT_SOURCE = (ROOT / "custom_components" / "renogy_ble" / "select.py").read_text()
SWITCH_SOURCE = (ROOT / "custom_components" / "renogy_ble" / "switch.py").read_text()


def test_riv_register_map_matches_capture() -> None:
    expected = {
        "BEEP": "0x1005",
        "OUTPUT": "0x1006",
        "CHARGE_CURRENT": "0x1146",
        "EQUALIZATION_VOLTAGE": "0x1149",
        "BOOST_VOLTAGE": "0x114A",
        "FLOAT_VOLTAGE": "0x114B",
        "LOW_VOLTAGE_WARN": "0x114E",
        "OVERDISCHARGE_SHUTDOWN": "0x114F",
        "OUTPUT_PRIORITY": "0x1159",
        "BATTERY_OVER_VOLTAGE": "0x1164",
        "OVERVOLTAGE_RECOVERY": "0x1165",
        "UNDERVOLTAGE_RECOVERY": "0x1166",
        "LITHIUM_ACTIVATION": "0x1169",
    }
    for name, value in expected.items():
        assert f"{name} = {value}" in CONST_SOURCE


def test_riv_switch_encodings_match_capture() -> None:
    assert 'key="inverter_beep"' in SWITCH_SOURCE
    assert "register=InverterRegister.BEEP" in SWITCH_SOURCE
    assert "on_value=0" in SWITCH_SOURCE
    assert "off_value=1" in SWITCH_SOURCE
    assert 'key="inverter_output"' in SWITCH_SOURCE
    assert "register=InverterRegister.OUTPUT" in SWITCH_SOURCE
    assert "off_value=2" in SWITCH_SOURCE
    assert 'key="inverter_lithium_activation"' in SWITCH_SOURCE
    assert "register=InverterRegister.LITHIUM_ACTIVATION" in SWITCH_SOURCE


def test_riv_output_priority_encodings_match_capture() -> None:
    assert '_VALUES = {"Grid First": 1, "Battery First": 2}' in SELECT_SOURCE
    assert "InverterRegister.OUTPUT_PRIORITY" in SELECT_SOURCE


def test_riv_charge_current_range() -> None:
    riv_block = NUMBER_SOURCE.split("RIV_INVERTER_NUMBERS", maxsplit=1)[1]
    charge_block = riv_block.split('key="inverter_charge_current"', maxsplit=1)[1]
    charge_block = charge_block.split("),", maxsplit=1)[0]
    assert "native_min_value=30.0" in charge_block
    assert "native_max_value=120.0" in charge_block
    assert "native_step=5.0" in charge_block
    assert "scale=10.0" in charge_block
