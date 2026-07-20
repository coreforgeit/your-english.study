from pydantic import BaseModel


class AudioTranscriptionResult(BaseModel):
    text: str
    model: str
    trim_duration_ms: float
    transcription_duration_ms: float
