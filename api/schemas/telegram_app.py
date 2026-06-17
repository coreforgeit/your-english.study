from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from db.models.enums import WordCountry, WordStatus


class TelegramWordsMode(StrEnum):
    LEARN = 'learn'
    REPEAT = 'repeat'


class TelegramWordsRequest(BaseModel):
    mode: TelegramWordsMode
    user_id: int | None = None
    level: str | None = None
    country: WordCountry | None = None


class WordRead(BaseModel):
    id: int
    word: str
    pronunciation: str | None
    translation: str
    part_of_speech: str | None
    country: WordCountry
    level: str | None
    audio_url: str | None
    audio_file_name: str | None
    audio_tg_id: str | None
    source: str | None
    status: WordStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TelegramWordsResponse(BaseModel):
    words: list[WordRead]
