class AIModuleError(Exception):
    """Base exception for AI module failures."""


class AudioTranscriptionError(AIModuleError):
    """Raised when audio transcription fails."""


class SpeechGenerationError(AIModuleError):
    """Raised when text-to-speech generation fails."""


class VocabularyReviewError(AIModuleError):
    """Raised when a vocabulary review cannot produce a structured result."""


class VocabularyAnswerCheckError(AIModuleError):
    """Raised when AI cannot produce a structured answer check."""
