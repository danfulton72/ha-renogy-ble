"""Constants for the Renogy BLE integration."""

import logging
from enum import Enum

DOMAIN = "renogy_ble"

LOGGER = logging.getLogger(__name__)

# BLE scanning constants
DEFAULT_SCAN_INTERVAL = 60  # seconds
MIN_SCAN_INTERVAL = 10  # seconds
MAX_SCAN_INTERVAL = 600  # seconds

# Availability grace: consecutive failed polls tolerated before the device is
# marked unavailable. Default matches RenogyBLEDevice.max_failures.
DEFAULT_MAX_FAILURES = 3
MIN_MAX_FAILURES = 1
MAX_MAX_FAILURES = 10

# Reconnect cooldown (minutes) before retrying a fully-unavailable device.
# Default matches renogy_ble's UNAVAILABLE_RETRY_INTERVAL.
DEFAULT_UNAVAILABLE_RETRY_INTERVAL = 10  # minutes
MIN_UNAVAILABLE_RETRY_INTERVAL = 1  # minutes
MAX_UNAVAILABLE_RETRY_INTERVAL = 60  # minutes

# Renogy BT-1 and BT-2 module identifiers - devices advertise with these prefixes
RENOGY_BT_PREFIX = "BT-TH-"
RENOGY_INVERTER_PREFIX = "RNGRIU"
RENOGY_REGO_INVERTER_PREFIX = "BTRIC"
RIV_INVERTER_MODEL_PREFIX = "RIV"
RENOGY_BATTERY_PRO_PREFIXES = ("RNGRBP", "RNGC", "RNGPRO")

# Configuration parameters
CONF_SCAN_INTERVAL = "scan_interval"
CONF_MAX_FAILURES = "max_failures"
CONF_UNAVAILABLE_RETRY_INTERVAL = "unavailable_retry_interval"
CONF_DEVICE_TYPE = "device_type"
CONF_DEVICE_NAME = "device_name"
CONF_SHUNT_CONNECTION_MODE = "shunt_connection_mode"
CONF_NON_SHUNT_CONNECTION_MODE = "non_shunt_connection_mode"
CONF_COMMUNICATION_HUB_ENABLED = "communication_hub_enabled"
DEFAULT_COMMUNICATION_HUB_ENABLED = False

# Device info
ATTR_MANUFACTURER = "Renogy"


class DeviceType(Enum):
    """Supported Renogy device types."""

    CONTROLLER = "controller"
    BATTERY = "battery"
    INVERTER = "inverter"
    DCC = "dcc"
    SHUNT300 = "shunt300"


DEVICE_TYPES = [e.value for e in DeviceType]
DEFAULT_DEVICE_TYPE = DeviceType.CONTROLLER.value


class ShuntConnectionMode(Enum):
    """Supported Smart Shunt connection strategies."""

    SUSTAINED = "sustained"
    INTERMITTENT = "intermittent"


SHUNT_CONNECTION_MODES = [mode.value for mode in ShuntConnectionMode]
DEFAULT_SHUNT_CONNECTION_MODE = ShuntConnectionMode.SUSTAINED.value


class NonShuntConnectionMode(Enum):
    """Supported non-shunt connection strategies."""

    INTERMITTENT = "intermittent"
    PERSISTENT_SESSION = "persistent_session"


NON_SHUNT_CONNECTION_MODES = [mode.value for mode in NonShuntConnectionMode]
DEFAULT_NON_SHUNT_CONNECTION_MODE = NonShuntConnectionMode.INTERMITTENT.value

SUPPORTED_DEVICE_TYPES = [
    DeviceType.CONTROLLER.value,
    DeviceType.BATTERY.value,
    DeviceType.DCC.value,
    DeviceType.INVERTER.value,
    DeviceType.SHUNT300.value,
]


class DCCRegister:
    """Modbus register addresses for DCC charger parameters."""

    MAX_CHARGING_CURRENT = 0xE001
    BATTERY_TYPE = 0xE004
    OVERVOLTAGE_THRESHOLD = 0xE005
    CHARGING_LIMIT_VOLTAGE = 0xE006
    EQUALIZATION_VOLTAGE = 0xE007
    BOOST_VOLTAGE = 0xE008
    FLOAT_VOLTAGE = 0xE009
    BOOST_RETURN_VOLTAGE = 0xE00A
    OVERDISCHARGE_RETURN_VOLTAGE = 0xE00B
    UNDERVOLTAGE_WARNING = 0xE00C
    OVERDISCHARGE_VOLTAGE = 0xE00D
    DISCHARGE_LIMIT_VOLTAGE = 0xE00E
    OVERDISCHARGE_DELAY = 0xE010
    EQUALIZATION_TIME = 0xE011
    BOOST_TIME = 0xE012
    EQUALIZATION_INTERVAL = 0xE013
    TEMPERATURE_COMPENSATION = 0xE014
    REVERSE_CHARGING_VOLTAGE = 0xE020
    SOLAR_CUTOFF_CURRENT = 0xE038


class InverterRegister:
    """Modbus registers for supported inverter settings."""

    # Shared/REGO settings.
    CHARGE_CURRENT = 0x1146
    LOW_VOLTAGE_WARN = 0x114E
    BATTERY_OVER_VOLTAGE = 0x1164
    AC_INPUT_CURRENT_LIMIT = 0x1168

    # RIV-series settings confirmed from Renogy app BLE captures.
    BEEP = 0x1005
    OUTPUT = 0x1006
    EQUALIZATION_VOLTAGE = 0x1149
    BOOST_VOLTAGE = 0x114A
    FLOAT_VOLTAGE = 0x114B
    OVERDISCHARGE_SHUTDOWN = 0x114F
    OUTPUT_PRIORITY = 0x1159
    OVERVOLTAGE_RECOVERY = 0x1165
    UNDERVOLTAGE_RECOVERY = 0x1166
    LITHIUM_ACTIVATION = 0x1169


DCC_BATTERY_TYPES = {
    0: "custom",
    1: "open",
    2: "sealed",
    3: "gel",
    4: "lithium",
}

DCC_BATTERY_TYPE_VALUES = {v: k for k, v in DCC_BATTERY_TYPES.items()}

DCC_MAX_CURRENT_OPTIONS = [10, 20, 30, 40, 50, 60]
DCC_MAX_CURRENT_TO_DEVICE = {amp: amp * 100 for amp in DCC_MAX_CURRENT_OPTIONS}
