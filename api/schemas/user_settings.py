from datetime import time

from pydantic import BaseModel, ConfigDict, field_validator

from enums import Timezone


class UserSettingsData(BaseModel):
    selected_language_level_id: int | None
    system_language_level_id: int | None
    reminders_enabled: bool
    timezone: Timezone | None
    reminder_time: time

    model_config = ConfigDict(from_attributes=True)


class UserSettingsUpdate(BaseModel):
    selected_language_level_id: int | None = None
    reminders_enabled: bool | None = None
    timezone: Timezone | None = None
    reminder_time: time | None = None

    model_config = ConfigDict(extra='forbid')

    @field_validator('reminders_enabled', 'reminder_time', mode='before')
    @classmethod
    def non_nullable_fields_must_not_be_null(cls, value: object) -> object:
        if value is None:
            raise ValueError('field must not be null')
        return value


class UserSettingsResponse(BaseModel):
    data: UserSettingsData
