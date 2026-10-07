"""Request body for on-demand goal simulation (Recalculate)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SimulateRequest(BaseModel):
    """Optional overrides; unset fields fall back to the goal's stored values."""

    target_value: float | None = Field(default=None, gt=0)
    monthly_contribution: float | None = Field(default=None, ge=0)
    num_paths: int | None = Field(default=None, ge=100, le=200_000)
    seed: int | None = Field(default=None, ge=0)


class RequiredContributionRequest(BaseModel):
    target_probability: float = Field(default=0.75, gt=0, lt=1)


class RequiredContributionRead(BaseModel):
    required_monthly_contribution: float
    probability_of_success: float
    target_probability: float
    reachable: bool


class StressScenarioRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    label: str
    shock: float
    probability_of_success: float
    median_ending_value: float
    p10_value: float


class StressTestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    baseline_probability: float
    scenarios: list[StressScenarioRead] = []


class JointOptimizeRequest(BaseModel):
    total_budget: float = Field(gt=0, le=5_000_000)
    max_steps: int = Field(default=16, ge=4, le=40)


class GoalAllocationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    goal_id: int
    goal_key: str
    goal_name: str
    allocated_monthly: float
    baseline_probability: float
    optimized_probability: float


class JointOptimizeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total_budget: float
    step: float
    allocations: list[GoalAllocationRead] = []
    expected_goals_before: float
    expected_goals_after: float
    on_track_after: int
    goal_count: int
    unallocated: float
