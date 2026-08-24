"""update word audio urls

Revision ID: 8c62f4a3d9e1
Revises: f6d53778d132
Create Date: 2026-08-24
"""

from collections.abc import Sequence
import json
from pathlib import Path
from urllib.parse import urlsplit

from alembic import op
import sqlalchemy as sa


revision: str = '8c62f4a3d9e1'
down_revision: str | None = 'f6d53778d132'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


AUDIO_URLS_PATH = (
    Path(__file__).resolve().parents[1]
    / 'seed_data'
    / 'r2_audio_urls.json'
)
BATCH_SIZE = 1000

WORDS_EN_TABLE = sa.table(
    'words_en',
    sa.column('id', sa.BigInteger),
    sa.column('word', sa.String),
    sa.column('audio_url', sa.String),
)


def upgrade() -> None:
    audio_paths_by_word = _read_audio_paths()
    connection = op.get_bind()
    words = connection.execute(
        sa.select(
            WORDS_EN_TABLE.c.id,
            WORDS_EN_TABLE.c.word,
        ),
    ).all()

    update_statement = (
        sa.update(WORDS_EN_TABLE)
        .where(WORDS_EN_TABLE.c.id == sa.bindparam('word_id'))
        .values(audio_url=sa.bindparam('new_audio_url'))
    )

    for start in range(0, len(words), BATCH_SIZE):
        chunk = words[start : start + BATCH_SIZE]
        values = [
            {
                'word_id': word.id,
                'new_audio_url': audio_paths_by_word.get(word.word),
            }
            for word in chunk
        ]
        connection.execute(update_statement, values)


def downgrade() -> None:
    # Предыдущие ссылки нельзя безопасно восстановить после обновления данных.
    pass


def _read_audio_paths() -> dict[str, str]:
    if not AUDIO_URLS_PATH.exists():
        raise FileNotFoundError(
            f'Файл со ссылками на аудио не найден: {AUDIO_URLS_PATH}',
        )

    try:
        with AUDIO_URLS_PATH.open(encoding='utf-8') as file:
            raw_audio_urls = json.load(file)
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(
            f'Не удалось прочитать файл со ссылками: {AUDIO_URLS_PATH}',
        ) from error

    if not isinstance(raw_audio_urls, dict):
        raise ValueError(
            f'Файл со ссылками должен содержать JSON-объект: {AUDIO_URLS_PATH}',
        )

    audio_paths: dict[str, str] = {}
    for raw_word, raw_audio_url in raw_audio_urls.items():
        if not isinstance(raw_word, str) or not isinstance(raw_audio_url, str):
            continue

        word = raw_word.strip()
        audio_path = _extract_audio_path(raw_audio_url)
        if word and audio_path is not None:
            audio_paths[word] = audio_path

    return audio_paths


def _extract_audio_path(audio_url: str) -> str | None:
    parsed_url = urlsplit(audio_url.strip())
    if parsed_url.scheme not in {'http', 'https'} or not parsed_url.netloc:
        return None

    normalized_path = f'/{parsed_url.path.lstrip("/")}'
    if normalized_path == '/':
        return None

    return normalized_path
