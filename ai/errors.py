class AIModuleError(Exception):
    """Base exception for AI module failures."""


class AudioTranscriptionError(AIModuleError):
    """Raised when audio transcription fails."""
