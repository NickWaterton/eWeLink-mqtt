from enum import IntEnum

class LightEntityFeature(IntEnum):
    """Supported features of the light entity."""

    EFFECT = 4
    FLASH = 8
    TRANSITION = 32


# These SUPPORT_* constants are deprecated as of Home Assistant 2022.5.
# Please use the LightEntityFeature enum instead.
SUPPORT_BRIGHTNESS = 1  # Deprecated, replaced by color modes
SUPPORT_COLOR_TEMP = 2  # Deprecated, replaced by color modes
SUPPORT_EFFECT = 4
SUPPORT_FLASH = 8
SUPPORT_COLOR = 16  # Deprecated, replaced by color modes
SUPPORT_TRANSITION = 32
SUPPORT_WHITE_VALUE = 128  # Deprecated, replaced by color modes

# Color mode of the light
ATTR_COLOR_MODE = "color_mode"
# List of color modes supported by the light
ATTR_SUPPORTED_COLOR_MODES = "supported_color_mode"
COLOR_MODE_BRIGHTNESS = None
COLOR_MODE_COLOR_TEMP = None
COLOR_MODE_RGB = None
COLOR_MODE_ONOFF = None

class LightEntity:
    pass