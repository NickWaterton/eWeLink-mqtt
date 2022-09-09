from enum import IntEnum

class FanEntityFeature(IntEnum):
    """Supported features of the fan entity."""

    SET_SPEED = 1
    OSCILLATE = 2
    DIRECTION = 4
    PRESET_MODE = 8


# These SUPPORT_* constants are deprecated as of Home Assistant 2022.5.
# Please use the FanEntityFeature enum instead.
SUPPORT_SET_SPEED = 1
SUPPORT_OSCILLATE = 2
SUPPORT_DIRECTION = 4
SUPPORT_PRESET_MODE = 8

SERVICE_INCREASE_SPEED = "increase_speed"
SERVICE_DECREASE_SPEED = "decrease_speed"
SERVICE_OSCILLATE = "oscillate"
SERVICE_SET_DIRECTION = "set_direction"
SERVICE_SET_PERCENTAGE = "set_percentage"
SERVICE_SET_PRESET_MODE = "set_preset_mode"

DIRECTION_FORWARD = "forward"
DIRECTION_REVERSE = "reverse"

ATTR_PERCENTAGE = "percentage"
ATTR_PERCENTAGE_STEP = "percentage_step"
ATTR_OSCILLATING = "oscillating"
ATTR_DIRECTION = "direction"
ATTR_PRESET_MODE = "preset_mode"
ATTR_PRESET_MODES = "preset_modes"


class NotValidPresetModeError(ValueError):
    """Exception class when the preset_mode in not in the preset_modes list."""

class FanEntity:
    pass
