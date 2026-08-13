from pydantic import BaseModel, ConfigDict, Field


class SessionData(BaseModel):
    user_id: int
    language_level: int | None = Field(ge=1, le=6)

    model_config = ConfigDict(extra='forbid')
