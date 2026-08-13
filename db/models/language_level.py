import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.models.base import Base


class LanguageLevel(Base):
    __tablename__ = 'language_levels'
    __table_args__ = (
        sa.CheckConstraint(
            'grade BETWEEN 1 AND 6',
            name='ck_language_levels_grade_range',
        ),
    )

    name: Mapped[str] = mapped_column(
        sa.String(10),
        unique=True,
        index=True,
    )
    grade: Mapped[int] = mapped_column(
        sa.SmallInteger,
        unique=True,
        index=True,
    )

    words: Mapped[list['WordEn']] = relationship(
        back_populates='language_level',
    )
