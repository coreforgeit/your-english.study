from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from enums import VocabularyAnswerVerdict


class AudioTranscriptionResult(BaseModel):
    text: str
    model: str
    trim_duration_ms: float
    transcription_duration_ms: float


class VocabularySynonym(BaseModel):
    model_config = ConfigDict(extra='forbid')

    word: str
    part_of_speech: str


class VocabularyReviewResult(BaseModel):
    model_config = ConfigDict(extra='forbid')

    translations: list[str]
    synonyms: list[VocabularySynonym]
    is_appropriate: bool
    level: Literal['A1', 'A2', 'B1', 'B2', 'C1', 'C2']


class VocabularyCreationResult(VocabularyReviewResult):
    part_of_speech: str


class VocabularyAnswerCheckResult(BaseModel):
    model_config = ConfigDict(extra='forbid')

    verdict: VocabularyAnswerVerdict
    comment: str | None = Field(default=None, max_length=200)
