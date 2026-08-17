from pydantic import BaseModel, ConfigDict, Field

from enums import AnswerLanguage, AnswerType, TextModel


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

    model_config = ConfigDict(from_attributes=True)


class VocabularyWordsResponse(BaseModel):
    data: WordRead


class VocabularyIntervalRepetitionsResponse(BaseModel):
    data: list[int]


class VocabularyWordAnswerRequest(BaseModel):
    word_id: int
    answer_type: AnswerType
    answer_language: AnswerLanguage
    answer: str | None = None
    skip: bool = False


class AnswerTypo(BaseModel):
    index: int
    type: str
    expected: str | None = None
    actual: str | None = None


class VocabularyWordAnswerData(BaseModel):
    success: bool
    answer: str
    correct_answer: str | None = None
    is_correct: bool | None = None
    skip: bool = False
    has_typo: bool = False
    typo: AnswerTypo | None = None


class VocabularyWordAnswerResponse(BaseModel):
    data: VocabularyWordAnswerData


class WordReviewResponse(BaseModel):
    success: bool


class WordReviewRequest(BaseModel):
    model: TextModel = TextModel.GPT_4O_MINI
    # model: TextModel = TextModel.GPT_5_6_LUNA
