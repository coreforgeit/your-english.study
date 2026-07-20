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


VOCABULARY_REVIEW_PROMPT = """
You are an English-Russian lexicographer for a general-audience language-learning app.
Analyze exactly the supplied English word for the supplied part of speech.

Return:
- translations: common, natural Russian translations for this part of speech only;
- synonyms: genuine English synonyms, each in its dictionary form and with its part of speech;
- is_appropriate: true only when this is a real English lexical item that is suitable to teach
  and display to a general audience. Return false for profanity, slurs, explicit or strongly
  offensive vocabulary, malformed/non-English input, and other entries unsuitable for learning.

Do not invent translations or synonyms. Do not include explanations. Keep translations and
synonyms unique. An uncommon or advanced word is not inappropriate merely because it is uncommon.
""".strip()


def get_transcription_prompt(language: str | None) -> str | None:
    if language is None:
        return None

    return TRANSCRIPTION_PROMPTS.get(language)
