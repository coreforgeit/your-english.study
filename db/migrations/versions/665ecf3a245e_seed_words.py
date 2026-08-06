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
down_revision: str | None = 'b0af56d0b8ea'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


WORDS_EN_TABLE = sa.table(
    'words_en',
    sa.column('id', sa.Integer),
    sa.column('word', sa.String),
    sa.column('pronunciation', sa.String),
    sa.column('part_of_speech', sa.String),
    sa.column('country', sa.String),
    sa.column('level', sa.String),
    sa.column('audio_url', sa.String),
    sa.column('source', sa.String),
)

WORDS_RU_TABLE = sa.table(
    'words_ru',
    sa.column('word_en_id', sa.Integer),
    sa.column('word', sa.String),
)

CSV_PATH = (
    Path(__file__).resolve().parents[1]
    / 'seed_data'
    / 'english_dictionary_full_cleaned.csv'
)
BATCH_SIZE = 1000


def upgrade() -> None:
    rows = list(_read_words_csv())
    connection = op.get_bind()

    for start in range(0, len(rows), BATCH_SIZE):
        chunk = rows[start : start + BATCH_SIZE]
        words_en_chunk = [
            _word_en_data(row)
            for row in chunk
        ]

        stmt = psql.insert(WORDS_EN_TABLE).values(words_en_chunk)
        stmt = stmt.on_conflict_do_update(
            index_elements=['word', 'part_of_speech'],
            set_={
                'pronunciation': stmt.excluded.pronunciation,
                'country': stmt.excluded.country,
                'level': stmt.excluded.level,
                'audio_url': stmt.excluded.audio_url,
                'source': stmt.excluded.source,
            },
        )
        connection.execute(stmt)

        word_ids = _get_word_en_ids(connection, words_en_chunk)
        words_ru_chunk = []
        for row in chunk:
            word_en_id = word_ids[(row['word'], row['part_of_speech'])]
            words_ru_chunk.extend(
                {
                    'word_en_id': word_en_id,
                    'word': translation,
                }
                for translation in row['translations']
            )

        if not words_ru_chunk:
            continue

        stmt = psql.insert(WORDS_RU_TABLE).values(words_ru_chunk)
        stmt = stmt.on_conflict_do_nothing(
            index_elements=['word_en_id', 'word'],
        )
        connection.execute(stmt)


def downgrade() -> None:
    word_keys = [
        (row['word'], row['part_of_speech'])
        for row in _read_words_csv()
    ]
    connection = op.get_bind()

    for start in range(0, len(word_keys), BATCH_SIZE):
        chunk = word_keys[start : start + BATCH_SIZE]
        word_ids = _get_word_en_ids_by_keys(connection, chunk)
        if word_ids:
            connection.execute(
                sa.delete(WORDS_RU_TABLE).where(
                    WORDS_RU_TABLE.c.word_en_id.in_(word_ids),
                ),
            )

        connection.execute(
            sa.delete(WORDS_EN_TABLE).where(
                sa.tuple_(
                    WORDS_EN_TABLE.c.word,
                    WORDS_EN_TABLE.c.part_of_speech,
                ).in_(chunk),
            ),
        )


def _read_words_csv() -> list[dict[str, str | None]]:
    if not CSV_PATH.exists():
        raise FileNotFoundError(f'Seed file not found: {CSV_PATH}')

    words_by_key: dict[tuple[str, str | None], dict[str, object]] = {}
    with CSV_PATH.open(encoding='utf-8-sig', newline='') as file:
        for row in csv.DictReader(file):
            normalized_row = _normalize_row(row)
            key = (
                normalized_row['word'],
                normalized_row['part_of_speech'],
            )
            words_by_key[key] = normalized_row

    return list(words_by_key.values())


def _normalize_row(row: dict[str, str | None]) -> dict[str, object]:
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
        'translations': _split_translations(row.get('translation')),
        'part_of_speech': _nullable(row.get('part_of_speech')),
        'country': country_map.get(_clean(row.get('country')), 'both'),
        'level': _nullable(row.get('level')),
        'audio_url': _nullable(row.get('audio_url')),
        'source': 'base',
    }


def _word_en_data(row: dict[str, object]) -> dict[str, str | None]:
    return {
        'word': row['word'],
        'pronunciation': row['pronunciation'],
        'part_of_speech': row['part_of_speech'],
        'country': row['country'],
        'level': row['level'],
        'audio_url': row['audio_url'],
        'source': row['source'],
    }


def _get_word_en_ids(
    connection: sa.Connection,
    rows: list[dict[str, str | None]],
) -> dict[tuple[str, str | None], int]:
    keys = [
        (row['word'], row['part_of_speech'])
        for row in rows
    ]
    result = connection.execute(
        sa.select(
            WORDS_EN_TABLE.c.id,
            WORDS_EN_TABLE.c.word,
            WORDS_EN_TABLE.c.part_of_speech,
        ).where(
            sa.tuple_(
                WORDS_EN_TABLE.c.word,
                WORDS_EN_TABLE.c.part_of_speech,
            ).in_(keys),
        ),
    )
    return {
        (row.word, row.part_of_speech): row.id
        for row in result
    }


def _get_word_en_ids_by_keys(
    connection: sa.Connection,
    keys: list[tuple[str, str | None]],
) -> list[int]:
    result = connection.execute(
        sa.select(WORDS_EN_TABLE.c.id).where(
            sa.tuple_(
                WORDS_EN_TABLE.c.word,
                WORDS_EN_TABLE.c.part_of_speech,
            ).in_(keys),
        ),
    )
    return [row.id for row in result]


def _split_translations(value: str | None) -> list[str]:
    cleaned = _clean(value)
    if cleaned is None:
        return []

    translations = [
        translation.strip()
        for translation in cleaned.replace(';', ',').replace('/', ',').split(',')
    ]
    return list(dict.fromkeys(translation for translation in translations if translation))


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
