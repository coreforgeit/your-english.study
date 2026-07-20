from pydantic import BaseModel, ConfigDict


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
