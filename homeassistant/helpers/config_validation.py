from typing import Any, TypeVar, cast, overload
import voluptuous as vol

# Home Assistant types
byte = vol.All(vol.Coerce(int), vol.Range(min=0, max=255))
small_float = vol.All(vol.Coerce(float), vol.Range(min=0, max=1))
positive_int = vol.All(vol.Coerce(int), vol.Range(min=0))
positive_float = vol.All(vol.Coerce(float), vol.Range(min=0))
latitude = vol.All(
    vol.Coerce(float), vol.Range(min=-90, max=90), msg="invalid latitude"
)
longitude = vol.All(
    vol.Coerce(float), vol.Range(min=-180, max=180), msg="invalid longitude"
)
gps = vol.ExactSequence([latitude, longitude])
#sun_event = vol.All(vol.Lower, vol.Any(SUN_EVENT_SUNSET, SUN_EVENT_SUNRISE))
port = vol.All(vol.Coerce(int), vol.Range(min=1, max=65535))

# typing typevar
_T = TypeVar("_T")

def string(value: Any) -> str:
    """Coerce value to string, except for None."""
    if value is None:
        raise vol.Invalid("string value is None")

    #if isinstance(value, template_helper.ResultWrapper):
    #    value = value.render_result

    elif isinstance(value, (list, dict)):
        raise vol.Invalid("value should be a string")

    return str(value)

'''
@overload
def ensure_list(value: None) -> list[Any]:
    ...


@overload
def ensure_list(value: list[_T]) -> list[_T]:
    ...


@overload
def ensure_list(value: list[_T] | _T) -> list[_T]:
    ...
'''

def ensure_list(value):
    """Wrap value in list if it is not one."""
    if value is None:
        return []
    return value if isinstance(value, list) else [value]