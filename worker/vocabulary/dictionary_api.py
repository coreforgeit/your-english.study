from dataclasses import dataclass
from urllib.parse import quote

import httpx


DICTIONARY_API_URL = 'https://api.dictionaryapi.dev/api/v2/entries/en/{word}'


@dataclass(frozen=True, slots=True)
class DictionaryWordData:
    audio_url: str | None
    pronunciation: str | None


async def get_dictionary_word_data(word: str) -> DictionaryWordData:
    url = DICTIONARY_API_URL.format(word=quote(word, safe=''))
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(url)

    if response.status_code == httpx.codes.NOT_FOUND:
        return DictionaryWordData(audio_url=None, pronunciation=None)

    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        return DictionaryWordData(audio_url=None, pronunciation=None)

    audio_url: str | None = None
    pronunciation: str | None = None

    for entry in payload:
        if not isinstance(entry, dict):
            continue

        entry_pronunciation = entry.get('phonetic')
        if not pronunciation and isinstance(entry_pronunciation, str):
            pronunciation = entry_pronunciation.strip() or None

        phonetics = entry.get('phonetics', [])
        if not isinstance(phonetics, list):
            continue

        for phonetic in phonetics:
            if not isinstance(phonetic, dict):
                continue

            phonetic_text = phonetic.get('text')
            if not pronunciation and isinstance(phonetic_text, str):
                pronunciation = phonetic_text.strip() or None

            audio = phonetic.get('audio')
            if not audio_url and isinstance(audio, str) and audio.strip():
                audio_url = audio.strip()
                if audio_url.startswith('//'):
                    audio_url = f'https:{audio_url}'

        if audio_url and pronunciation:
            break

    return DictionaryWordData(
        audio_url=audio_url,
        pronunciation=pronunciation,
    )
