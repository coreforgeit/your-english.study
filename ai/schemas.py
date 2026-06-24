from pydantic import BaseModel


class AudioTranscriptionResult(BaseModel):
    text: str
    model: str
