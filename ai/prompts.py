TRANSCRIPTION_PROMPTS = {
    'en': (
        'The speaker is answering an English vocabulary exercise. '
        'Transcribe only the spoken English word or phrase. '
        'Use Latin letters only. '
        'Return only the transcription.'
    ),
    'ru': (
        'Transcribe the audio as Russian text. '
        'Use Cyrillic only. '
        'Do not translate to English. '
        'Return only the transcription.'
    ),
}


def get_transcription_prompt(language: str | None) -> str | None:
    if language is None:
        return None

    return TRANSCRIPTION_PROMPTS.get(language)
