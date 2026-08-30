"""Regression tests for RIV inverter controls."""

from custom_components.renogy_ble.const import InverterRegister
from custom_components.renogy_ble.number import RIV_INVERTER_NUMBERS
from custom_components.renogy_ble.select import RenogyOutputPrioritySelect
from custom_components.renogy_ble.switch import RIV_SWITCHES


def test_riv_register_map_matches_capture() -> None:
    """Pin registers decoded from the Renogy Android HCI capture."""
    assert InverterRegister.BEEP == 0x1005
    assert InverterRegister.OUTPUT == 0x1006
    assert InverterRegister.CHARGE_CURRENT == 0x1146
    assert InverterRegister.EQUALIZATION_VOLTAGE == 0x1149
    assert InverterRegister.BOOST_VOLTAGE == 0x114A
    assert InverterRegister.FLOAT_VOLTAGE == 0x114B
    assert InverterRegister.LOW_VOLTAGE_WARN == 0x114E
    assert InverterRegister.OVERDISCHARGE_SHUTDOWN == 0x114F
    assert InverterRegister.OUTPUT_PRIORITY == 0x1159
    assert InverterRegister.BATTERY_OVER_VOLTAGE == 0x1164
    assert InverterRegister.OVERVOLTAGE_RECOVERY == 0x1165
    assert InverterRegister.UNDERVOLTAGE_RECOVERY == 0x1166
    assert InverterRegister.LITHIUM_ACTIVATION == 0x1169


def test_riv_switch_encodings_match_capture() -> None:
    """Use the exact ON/OFF values observed in the app traffic."""
    by_key = {item.key: item for item in RIV_SWITCHES}

    assert (by_key["inverter_beep"].on_value, by_key["inverter_beep"].off_value) == (
        0,
        1,
    )
    assert (
        by_key["inverter_output"].on_value,
        by_key["inverter_output"].off_value,
    ) == (1, 2)
    assert (
        by_key["inverter_lithium_activation"].on_value,
        by_key["inverter_lithium_activation"].off_value,
    ) == (1, 0)


def test_riv_output_priority_encodings_match_capture() -> None:
    """Map the two app output-priority choices to their captured values."""
    assert RenogyOutputPrioritySelect._VALUES == {
        "Grid First": 1,
        "Battery First": 2,
    }


def test_riv_charge_current_range() -> None:
    """Limit RIV1230PCH charge current to the requested supported range."""
    charge = next(
        item for item in RIV_INVERTER_NUMBERS if item.key == "inverter_charge_current"
    )

    assert charge.native_min_value == 30.0
    assert charge.native_max_value == 120.0
    assert charge.native_step == 5.0
    assert charge.scale == 10.0
