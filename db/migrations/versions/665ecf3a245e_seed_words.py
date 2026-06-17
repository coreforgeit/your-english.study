"""seed words

Revision ID: 665ecf3a245e
Revises: e197b367fe3d
Create Date: 2026-06-17 11:52:36.248489+00:00
"""

from collections.abc import Sequence
import csv
from pathlib import Path

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as psql


revision: str = '665ecf3a245e'
down_revision: str | None = 'e197b367fe3d'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


WORDS_TABLE = sa.table(
    'words',
    sa.column('word', sa.String),
    sa.column('pronunciation', sa.String),
    sa.column('translation', sa.String),
    sa.column('part_of_speech', sa.String),
    sa.column('country', sa.String),
    sa.column('level', sa.String),
    sa.column('audio_url', sa.String),
    sa.column('source', sa.String),
)

CSV_PATH = (
    Path(__file__).resolve().parents[1]
    / 'seed_data'
    / 'english_dictionary_full.csv'
)
BATCH_SIZE = 1000


def upgrade() -> None:
    rows = list(_read_words_csv())
    connection = op.get_bind()

    for start in range(0, len(rows), BATCH_SIZE):
        chunk = rows[start : start + BATCH_SIZE]
        stmt = psql.insert(WORDS_TABLE).values(chunk)
        stmt = stmt.on_conflict_do_update(
            index_elements=['word', 'part_of_speech'],
            set_={
                'pronunciation': stmt.excluded.pronunciation,
                'translation': stmt.excluded.translation,
                'country': stmt.excluded.country,
                'level': stmt.excluded.level,
                'audio_url': stmt.excluded.audio_url,
                'source': stmt.excluded.source,
            },
        )
        connection.execute(stmt)


def downgrade() -> None:
    words = [
        (row['word'], row['part_of_speech'])
        for row in _read_words_csv()
    ]
    connection = op.get_bind()

    for start in range(0, len(words), BATCH_SIZE):
        chunk = words[start : start + BATCH_SIZE]
        connection.execute(
            sa.delete(WORDS_TABLE).where(
                sa.tuple_(
                    WORDS_TABLE.c.word,
                    WORDS_TABLE.c.part_of_speech,
                ).in_(chunk),
            ),
        )


def _read_words_csv() -> list[dict[str, str | None]]:
    if not CSV_PATH.exists():
        raise FileNotFoundError(f'Seed file not found: {CSV_PATH}')

    words_by_key: dict[tuple[str, str | None], dict[str, str | None]] = {}
    with CSV_PATH.open(encoding='utf-8-sig', newline='') as file:
        for row in csv.DictReader(file):
            normalized_row = _normalize_row(row)
            key = (
                normalized_row['word'],
                normalized_row['part_of_speech'],
            )
            words_by_key[key] = normalized_row

    return list(words_by_key.values())


def _normalize_row(row: dict[str, str | None]) -> dict[str, str | None]:
    country_map = {
        'US': 'us',
        'BR': 'gb',
        'both': 'both',
        '': 'both',
        None: 'both',
    }

    return {
        'word': _required(row.get('word'), 'word'),
        'pronunciation': _nullable(row.get('pronunciation')),
        'translation': _clean(row.get('translation')) or '',
        'part_of_speech': _nullable(row.get('part_of_speech')),
        'country': country_map.get(_clean(row.get('country')), 'both'),
        'level': _nullable(row.get('level')),
        'audio_url': _nullable(row.get('audio_url')),
        'source': 'default',
    }


def _required(value: str | None, field: str) -> str:
    cleaned = _clean(value)
    if cleaned is None:
        raise ValueError(f'Missing required field: {field}')
    return cleaned


def _nullable(value: str | None) -> str | None:
    return _clean(value)


def _clean(value: str | None) -> str | None:
    if value is None:
        return None

    cleaned = value.strip()
    return cleaned or None
