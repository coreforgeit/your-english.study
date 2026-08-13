"""backfill missing word levels

Revision ID: 1f6b5d2a8c41
Revises: 9cc445da784e
Create Date: 2026-08-13
"""

import csv
from collections.abc import Sequence
from pathlib import Path

from alembic import op
import sqlalchemy as sa


revision: str = '1f6b5d2a8c41'
down_revision: str | None = '9cc445da784e'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


CSV_PATH = (
    Path(__file__).resolve().parents[1]
    / 'seed_data'
    / 'english_dictionary_full_cleaned.csv'
)

LANGUAGE_LEVELS_TABLE = sa.table(
    'language_levels',
    sa.column('id', sa.BigInteger),
    sa.column('name', sa.String),
)

WORDS_EN_TABLE = sa.table(
    'words_en',
    sa.column('id', sa.BigInteger),
    sa.column('word', sa.String),
    sa.column('part_of_speech', sa.String),
    # sa.column('level', sa.String),
    sa.column('level_id', sa.BigInteger),
    sa.column('is_reviewed', sa.Boolean),
)


def upgrade() -> None:
    _backfill_missing_word_levels()


def downgrade() -> None:
    # The restored data cannot be safely distinguished from later changes.
    pass


def _backfill_missing_word_levels() -> None:
    connection = op.get_bind()
    level_ids_by_name = _get_level_ids_by_name(connection)
    csv_levels_by_word = _get_csv_levels_by_word(
        allowed_levels=set(level_ids_by_name),
    )

    words_without_level = connection.execute(
        sa.select(
            WORDS_EN_TABLE.c.id,
            WORDS_EN_TABLE.c.word,
            WORDS_EN_TABLE.c.part_of_speech,
        ).where(WORDS_EN_TABLE.c.level_id.is_(None)),
    ).all()

    for word in words_without_level:
        values: dict[str, object] = {'is_reviewed': False}
        key = (
            _normalize_word(word.word),
            _normalize_part_of_speech(word.part_of_speech),
        )
        level_name = csv_levels_by_word.get(key)

        if level_name is not None:
            # values['level'] = level_name
            values['level_id'] = level_ids_by_name[level_name]

        connection.execute(
            sa.update(WORDS_EN_TABLE)
            .where(WORDS_EN_TABLE.c.id == word.id)
            .values(**values),
        )


def _get_level_ids_by_name(connection: sa.Connection) -> dict[str, int]:
    language_levels = connection.execute(
        sa.select(
            LANGUAGE_LEVELS_TABLE.c.id,
            LANGUAGE_LEVELS_TABLE.c.name,
        ),
    ).all()
    return {
        _normalize_level(language_level.name): language_level.id
        for language_level in language_levels
    }


def _get_csv_levels_by_word(
    *,
    allowed_levels: set[str],
) -> dict[tuple[str, str | None], str]:
    if not CSV_PATH.exists():
        raise FileNotFoundError(f'Seed file not found: {CSV_PATH}')

    levels_by_word: dict[tuple[str, str | None], str] = {}
    with CSV_PATH.open(encoding='utf-8-sig', newline='') as file:
        for row in csv.DictReader(file):
            level_name = _normalize_nullable_level(row.get('level'))
            if level_name is None or level_name not in allowed_levels:
                continue

            key = (
                _normalize_word(row.get('word')),
                _normalize_part_of_speech(row.get('part_of_speech')),
            )
            if not key[0]:
                continue

            # Keep the first non-empty level; later empty duplicates cannot erase it.
            levels_by_word.setdefault(key, level_name)

    return levels_by_word


def _normalize_word(value: str | None) -> str:
    return ' '.join((value or '').split()).casefold()


def _normalize_part_of_speech(value: str | None) -> str | None:
    normalized = ' '.join((value or '').split()).casefold()
    return normalized or None


def _normalize_level(value: str) -> str:
    return value.strip().upper()


def _normalize_nullable_level(value: str | None) -> str | None:
    if value is None:
        return None

    normalized = _normalize_level(value)
    return normalized or None
