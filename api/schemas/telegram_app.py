from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class TelegramWordsRequest(BaseModel):
    level: str | None = None


class WordRead(BaseModel):
    id: int
    word: str
    pronunciation: str | None
    translation: str
    part_of_speech: str | None
    level: str | None
    audio_url: str | None

    model_config = ConfigDict(from_attributes=True)


class TelegramWordsResponse(BaseModel):
    data: WordRead


class AnswerType(StrEnum):
    TEXT = 'text'
    AUDIO = 'audio'


class AnswerLanguage(StrEnum):
    EN = 'en'
    RU = 'ru'


class TelegramWordAnswerRequest(BaseModel):
    word_id: int
    answer_type: AnswerType
    answer_language: AnswerLanguage
    answer: str | None = None


class AnswerTypo(BaseModel):
    index: int
    type: str
    expected: str | None = None
    actual: str | None = None


class TelegramWordAnswerData(BaseModel):
    success: bool
    answer: str
    is_correct: bool | None = None
    has_typo: bool = False
    typo: AnswerTypo | None = None


class TelegramWordAnswerResponse(BaseModel):
    data: TelegramWordAnswerData
