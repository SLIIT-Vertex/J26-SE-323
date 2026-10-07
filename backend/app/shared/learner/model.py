from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, SmallInteger, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database.base import Base


class LearnerModel(Base):
    __tablename__ = "learners"
    __table_args__ = (CheckConstraint("grade IN (4, 5)", name="ck_learners_grade"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    grade: Mapped[int] = mapped_column(SmallInteger)
    preferred_language: Mapped[str] = mapped_column(String(10))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

