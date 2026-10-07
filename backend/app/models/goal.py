"""Financial goal definitions and cached Monte Carlo simulation results."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Goal(Base, TimestampMixin):
    """A savings goal with a horizon and assigned investment vehicles."""

    __tablename__ = "goal"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)

    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    checkpoint_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    target_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    monthly_contribution: Mapped[float] = mapped_column(
        Float, default=0.0, nullable=False
    )

    # Assigned vehicles: MF ISINs and/or bucket names funding this goal.
    assigned_isins: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    assigned_buckets: Mapped[list[str]] = mapped_column(
        JSON, default=list, nullable=False
    )

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    simulations: Mapped[list[GoalSimulation]] = relationship(
        back_populates="goal",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class GoalSimulation(Base):
    """Cached output of a risk-engine Monte Carlo run for a goal.

    ``input_hash`` fingerprints the simulation inputs so the risk engine is not
    re-run on every page load — only when the inputs actually change.
    """

    __tablename__ = "goal_simulation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    goal_id: Mapped[int] = mapped_column(
        ForeignKey("goal.id", ondelete="CASCADE"), index=True, nullable=False
    )
    input_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    run_ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    probability_of_success: Mapped[float] = mapped_column(Float, nullable=False)
    median_ending_value: Mapped[float] = mapped_column(Float, nullable=False)
    p10_value: Mapped[float] = mapped_column(Float, nullable=False)
    p90_value: Mapped[float] = mapped_column(Float, nullable=False)

    goal: Mapped[Goal] = relationship(back_populates="simulations")
