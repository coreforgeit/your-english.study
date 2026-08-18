from dataclasses import dataclass

from fastapi import HTTPException, Request, status
from pydantic import ValidationError
from starlette.datastructures import UploadFile

from api.schemas.vocabulary import VocabularyWordAnswerRequest
from api.services.vocabulary_answer import AudioAnswerFile


@dataclass(frozen=True, slots=True)
class ParsedVocabularyAnswerRequest:
    payload: VocabularyWordAnswerRequest
    audio_file: AudioAnswerFile | None


async def parse_vocabulary_answer_request(
    request: Request,
) -> ParsedVocabularyAnswerRequest:
    try:
        raw_payload, audio_file = await _read_request_data(request)
        payload = VocabularyWordAnswerRequest.model_validate(raw_payload)
    except (TypeError, ValueError) as exc:
        detail = exc.errors() if isinstance(exc, ValidationError) else str(exc)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
        ) from exc

    return ParsedVocabularyAnswerRequest(
        payload=payload,
        audio_file=audio_file,
    )


async def _read_request_data(
    request: Request,
) -> tuple[dict[str, object], AudioAnswerFile | None]:
    content_type = request.headers.get('content-type', '')
    if not content_type.startswith('multipart/form-data'):
        return await request.json(), None

    form = await request.form()
    raw_audio_file = form.get('audio_file')
    audio_file = None
    if isinstance(raw_audio_file, UploadFile):
        audio_file = AudioAnswerFile(
            content=await raw_audio_file.read(),
            filename=raw_audio_file.filename or 'answer.webm',
            content_type=raw_audio_file.content_type or 'audio/webm',
        )

    return (
        {
            'word_id': form.get('word_id'),
            'answer_type': form.get('answer_type'),
            'answer_language': form.get('answer_language'),
            'text_answer': form.get('text_answer'),
            'skip': form.get('skip', False),
        },
        audio_file,
    )
