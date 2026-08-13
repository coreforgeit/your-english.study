import re
from enum import StrEnum
from zoneinfo import available_timezones


def _timezone_member_name(value: str) -> str:
    value = value.replace('+', '_PLUS_').replace('-', '_MINUS_')
    return re.sub(r'[^A-Za-z0-9]+', '_', value).strip('_').upper()


# IANA identifiers are stored as values, for example Europe/Moscow.
# They can be passed directly to zoneinfo.ZoneInfo for date and time conversion.
Timezone = StrEnum(
    'Timezone',
    {
        _timezone_member_name(timezone): timezone
        for timezone in sorted(available_timezones())
    },
    module=__name__,
)

