from enum import IntEnum

ATTR_ACTIVITY = "activity"
ATTR_ACTIVITY_LIST = "activity_list"
ATTR_CURRENT_ACTIVITY = "current_activity"
ATTR_COMMAND_TYPE = "command_type"
ATTR_DEVICE = "device"
ATTR_NUM_REPEATS = "num_repeats"
ATTR_DELAY_SECS = "delay_secs"
ATTR_HOLD_SECS = "hold_secs"
ATTR_ALTERNATIVE = "alternative"
ATTR_TIMEOUT = "timeout"

DEFAULT_NUM_REPEATS = 1
DEFAULT_DELAY_SECS = 0.4
DEFAULT_HOLD_SECS = 0

class RemoteEntityFeature(IntEnum):
    """Supported features of the remote entity."""

    LEARN_COMMAND = 1
    DELETE_COMMAND = 2
    ACTIVITY = 4


# These SUPPORT_* constants are deprecated as of Home Assistant 2022.5.
# Please use the RemoteEntityFeature enum instead.
SUPPORT_LEARN_COMMAND = 1
SUPPORT_DELETE_COMMAND = 2
SUPPORT_ACTIVITY = 4

class RemoteEntity:
    pass