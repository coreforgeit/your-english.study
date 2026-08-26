from urllib.parse import urljoin, urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator

from core.config import settings
from enums import AnswerLanguage, AnswerType, TextModel, WordStatus


class VocabularyWordsRequest(BaseModel):
    pass


class VocabularyRepeatWordRequest(VocabularyWordsRequest):
    word_id: int | None = Field(default=None, gt=0)


class WordRead(BaseModel):
    id: int
    word: str
    pronunciation: str | None
    translations: list[str] = Field(validation_alias='translation_words')
    part_of_speech: str | None
    level: str | None
    audio_url: str | None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @field_validator('audio_url', mode='before')
    @classmethod
    def build_audio_url(cls, value: str | None) -> str | None:
        if value is None:
            return None

        audio_path = value.strip()
        if not audio_path:
            return None

        parsed_url = urlsplit(audio_path)
        if parsed_url.scheme and parsed_url.netloc:
            return audio_path

        media_url = f'{settings.media_url.rstrip("/")}/'
        return urljoin(media_url, audio_path.lstrip('/'))


class VocabularyRepeatWordData(WordRead):
    answer_language: AnswerLanguage


class VocabularyWordAnswerRequest(BaseModel):
    word_id: int
    answer_type: AnswerType
    answer_language: AnswerLanguage
    text_answer: str | None = None
    skip: bool = False


class AnswerTypo(BaseModel):
    index: int
    type: str
    expected: str | None = None
    actual: str | None = None


class VocabularyWordAnswerData(BaseModel):
    success: bool
    answer: str
    correct_answer: list[str] = Field(default_factory=list, max_length=3)
    is_correct: bool | None = None
    skip: bool = False
    has_typo: bool = False
    typo: AnswerTypo | None = None
    comment: str | None = None


class VocabularyWordStatusData(BaseModel):
    id: int
    status: WordStatus


class WordReviewResponse(BaseModel):
    success: bool


class WordReviewRequest(BaseModel):
    model: TextModel = TextModel.GPT_4O_MINI
    # model: TextModel = TextModel.GPT_5_6_LUNA
