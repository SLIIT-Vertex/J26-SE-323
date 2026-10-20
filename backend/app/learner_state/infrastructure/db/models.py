from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database.base import Base


class LearnerSkillStateModel(Base):
    """
    Latest learner-state result for one learner and one skill.

    `skill_id` is the skill the learner was working on, sent by the client.
    It is stored as a label only and has no foreign key to another module's table.
    """

    __tablename__ = "learner_skill_states"
    __table_args__ = (
        CheckConstraint(
            "support_need IS NULL OR support_need BETWEEN 0 AND 1",
            name="ck_learner_skill_states_support_need",
        ),
    )

    learner_id: Mapped[UUID] = mapped_column(ForeignKey("learners.id"), primary_key=True)
    skill_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(100))
    # 64-bit: in-process game callers use the scoring time in milliseconds as the window id.
    window_id: Mapped[int] = mapped_column(BigInteger)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    confusion_state: Mapped[str] = mapped_column(String(40))
    confusion_support_need: Mapped[str] = mapped_column(String(40))
    confusion_temporal_score: Mapped[float] = mapped_column(Float)
    disengagement_state: Mapped[str] = mapped_column(String(40))
    disengagement_support_need: Mapped[str] = mapped_column(String(40))
    recommended_action: Mapped[str] = mapped_column(String(40))
    support_need: Mapped[float | None] = mapped_column(Float)  # null while confusion is uncertain
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
