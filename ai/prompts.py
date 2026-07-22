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


DIRECT_SYNONYM_RULES = """
Synonym rules:
- Return zero to three direct, obvious synonyms for the same specific sense and part of speech.
- A synonym must be safely interchangeable with the word in a simple neutral sentence without a
  material change in meaning, grammar, or register.
- Exclude merely related words, associations, collocations, examples, types, broader or narrower
  terms, and alternatives that work only in a special context.
- When uncertain, omit the candidate. An empty synonyms list is better than a loose synonym.
""".strip()


VOCABULARY_REVIEW_PROMPT = f"""
You are an English-Russian lexicographer for a general-audience language-learning app.
Analyze exactly the supplied English word for the supplied part of speech. Choose one primary,
common dictionary sense. Translation variants must express that same sense, not different senses
of the word.

Return:
- translations: common, natural Russian translations for the selected sense only;
- synonyms: direct English synonyms, each in its dictionary form and with its part of speech;
- level: the CEFR level A1, A2, B1, B2, C1, or C2 for learning this word in this sense;
- is_appropriate: true only when this is a real English lexical item that is suitable to teach
  and display to a general audience. Return false for profanity, slurs, explicit or strongly
  offensive vocabulary, malformed/non-English input, and other entries unsuitable for learning.

{DIRECT_SYNONYM_RULES}

Do not invent translations or synonyms. Do not include explanations. Keep translations and
synonyms unique. An uncommon or advanced word is not inappropriate merely because it is uncommon.
""".strip()


VOCABULARY_CREATION_PROMPT = f"""
You are an English-Russian lexicographer for a general-audience language-learning app.
Analyze the supplied English word as one vocabulary entry. If a part-of-speech hint is supplied,
use that part of speech. Otherwise, choose the most common general-use part of speech. Choose one
primary, common dictionary sense. Translation variants must express that same sense, not different
senses of the word.

Return:
- part_of_speech: the full lowercase English name, for example noun, verb, adjective, or adverb;
- translations: common, natural Russian translations for the selected sense only;
- synonyms: direct English synonyms in dictionary form, each with its part of speech;
- level: the CEFR level A1, A2, B1, B2, C1, or C2 for learning this word in this sense;
- is_appropriate: true only when this is a real English lexical item suitable to teach and display
  to a general audience. Return false for profanity, slurs, explicit or strongly offensive
  vocabulary, malformed/non-English input, and other entries unsuitable for learning.

{DIRECT_SYNONYM_RULES}

Do not invent translations or synonyms. Do not include explanations. Keep all lists unique.
""".strip()


def get_transcription_prompt(language: str | None) -> str | None:
    if language is None:
        return None

    return TRANSCRIPTION_PROMPTS.get(language)
