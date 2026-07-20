import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class AudioAnswerSampleService:
    def __init__(self, base_dir: Path | None = None) -> None:
        app_root = Path(__file__).resolve().parents[2]
        self.base_dir = base_dir or app_root / 'experiments' / 'audio_transcription' / 'samples'

    def save(
        self,
        *,
        audio: bytes,
        request_data: dict[str, Any],
        response_data: dict[str, Any],
        answer_language: str,
        transcription: str,
        original_filename: str,
        user_id: int,
    ) -> Path:
        language_dir = self.base_dir / answer_language
        language_dir.mkdir(parents=True, exist_ok=True)

        suffix = Path(original_filename).suffix or '.webm'
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        safe_transcription = self._safe_filename_part(transcription)
        word_id = request_data.get('word_id', 'unknown')
        audio_filename = f'{safe_transcription}_word-{word_id}_user-{user_id}_{timestamp}{suffix}'
        audio_path = language_dir / audio_filename
        audio_path.write_bytes(audio)

        manifest_path = language_dir / 'requests.json'
        entries = self._read_manifest(manifest_path)
        entries.append(
            {
                'created_at': timestamp,
                'audio_path': audio_filename,
                'request': request_data,
                'response': response_data,
            },
        )
        manifest_path.write_text(
            json.dumps(entries, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )
        return audio_path

    @staticmethod
    def _read_manifest(manifest_path: Path) -> list[dict[str, Any]]:
        if not manifest_path.exists():
            return []

        try:
            data = json.loads(manifest_path.read_text(encoding='utf-8'))
        except json.JSONDecodeError:
            return []

        if not isinstance(data, list):
            return []

        return [item for item in data if isinstance(item, dict)]

    @staticmethod
    def _safe_filename_part(value: str) -> str:
        cleaned = re.sub(r'[^\w-]+', '_', value.strip().lower(), flags=re.UNICODE).strip('_')
        return (cleaned or 'empty_transcription')[:80]
