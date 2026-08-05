from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator


Timezone = Annotated[
    str,
    Field(
        min_length=1,
        max_length=64,
        pattern=r'^[A-Za-z0-9._+-]+(?:/[A-Za-z0-9._+-]+)*$',
    ),
]


class UserSettingsData(BaseModel):
    timezone: Timezone

    model_config = ConfigDict(from_attributes=True)


class UserSettingsUpdate(BaseModel):
    timezone: Timezone | None = None

    model_config = ConfigDict(extra='forbid')

    @field_validator('timezone', mode='before')
    @classmethod
    def timezone_must_not_be_null(cls, value: object) -> object:
        if value is None:
            raise ValueError('timezone must not be null')
        return value


class UserSettingsResponse(BaseModel):
    data: UserSettingsData
