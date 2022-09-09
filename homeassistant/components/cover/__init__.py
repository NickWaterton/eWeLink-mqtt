from homeassistant.backports.enum import StrEnum

class CoverEntity:
    pass
    
class CoverDeviceClass(StrEnum):
    """Device class for cover."""

    # Refer to the cover dev docs for device class descriptions
    AWNING = "awning"
    BLIND = "blind"
    CURTAIN = "curtain"
    DAMPER = "damper"
    DOOR = "door"
    GARAGE = "garage"
    GATE = "gate"
    SHADE = "shade"
    SHUTTER = "shutter"
    WINDOW = "window"