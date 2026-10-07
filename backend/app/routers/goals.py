"""Goals CRUD endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.config import get_settings
from app.dependencies import DbSession, RiskDep
from app.models.goal import Goal
from app.schemas.analytics import GoalSimulationRead
from app.schemas.goal import GoalCreate, GoalRead, GoalUpdate
from app.schemas.simulate import (
    JointOptimizeRead,
    JointOptimizeRequest,
    RequiredContributionRead,
    RequiredContributionRequest,
    SimulateRequest,
    StressTestRead,
)
from app.services.analytics_service import latest_holding_views, today_ist
from app.services.goal_simulation import (
    SimulationOverrides,
    optimize_across_goals,
    simulate_goal_and_cache,
    solve_required_contribution,
    stress_test_goal,
)

router = APIRouter(prefix="/api/goals", tags=["goals"])


async def _get_or_404(db: DbSession, goal_id: int) -> Goal:
    goal = await db.get(Goal, goal_id)
    if goal is None:
        raise HTTPException(status_code=404, detail="Goal not found.")
    return goal


@router.get("", response_model=list[GoalRead])
async def list_goals(db: DbSession) -> list[Goal]:
    result = await db.execute(select(Goal).order_by(Goal.id))
    return list(result.scalars().all())


@router.get("/{goal_id}", response_model=GoalRead)
async def get_goal(goal_id: int, db: DbSession) -> Goal:
    return await _get_or_404(db, goal_id)


@router.post("", response_model=GoalRead, status_code=201)
async def create_goal(payload: GoalCreate, db: DbSession) -> Goal:
    existing = await db.execute(select(Goal).where(Goal.key == payload.key))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=409, detail=f"Goal with key '{payload.key}' already exists."
        )
    goal = Goal(**payload.model_dump())
    db.add(goal)
    await db.commit()
    await db.refresh(goal)
    return goal


@router.put("/{goal_id}", response_model=GoalRead)
async def update_goal(goal_id: int, payload: GoalUpdate, db: DbSession) -> Goal:
    goal = await _get_or_404(db, goal_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(goal, field, value)
    await db.commit()
    await db.refresh(goal)
    return goal


@router.delete("/{goal_id}", status_code=204)
async def delete_goal(goal_id: int, db: DbSession) -> None:
    goal = await _get_or_404(db, goal_id)
    await db.delete(goal)
    await db.commit()


@router.post("/{goal_id}/simulate", response_model=GoalSimulationRead)
async def simulate_goal(
    goal_id: int,
    db: DbSession,
    risk: RiskDep,
    payload: SimulateRequest | None = None,
) -> GoalSimulationRead:
    """Run a fresh Monte Carlo simulation for a goal and cache the result."""
    goal = await _get_or_404(db, goal_id)
    holdings_data = await latest_holding_views(db)
    holdings = holdings_data[0] if holdings_data is not None else []

    overrides = SimulationOverrides(
        target_value=payload.target_value if payload else None,
        monthly_contribution=payload.monthly_contribution if payload else None,
        # The public demo always runs the server's path count — a client-chosen
        # 200k-path run is the cheapest way to tie up the engine.
        num_paths=payload.num_paths if payload and not get_settings().demo_mode else None,
        seed=payload.seed if payload else None,
    )
    row = await simulate_goal_and_cache(
        db, goal, holdings, risk, today_ist(), get_settings().simulation_paths, overrides
    )
    if row is None:
        raise HTTPException(
            status_code=422,
            detail="Goal needs a target value and target date to simulate.",
        )
    return GoalSimulationRead.model_validate(row)


@router.post("/{goal_id}/required-contribution", response_model=RequiredContributionRead)
async def required_contribution(
    goal_id: int,
    db: DbSession,
    risk: RiskDep,
    payload: RequiredContributionRequest | None = None,
) -> RequiredContributionRead:
    """Solve for the monthly contribution needed to hit a target probability."""
    goal = await _get_or_404(db, goal_id)
    holdings_data = await latest_holding_views(db)
    holdings = holdings_data[0] if holdings_data is not None else []
    target_prob = payload.target_probability if payload else 0.75

    result = await solve_required_contribution(
        goal,
        holdings,
        risk,
        today_ist(),
        get_settings().simulation_paths,
        target_probability=target_prob,
    )
    if result is None:
        raise HTTPException(
            status_code=422,
            detail="Goal needs a target value and target date to solve.",
        )
    return RequiredContributionRead(
        required_monthly_contribution=result.required_monthly_contribution,
        probability_of_success=result.probability_of_success,
        target_probability=result.target_probability,
        reachable=result.reachable,
    )


@router.post("/optimize", response_model=JointOptimizeRead)
async def optimize_goals(
    db: DbSession, risk: RiskDep, payload: JointOptimizeRequest
) -> JointOptimizeRead:
    """Phase 53: split one monthly budget across all goals to lift the weakest first."""
    result = await db.execute(select(Goal).order_by(Goal.id))
    goals = list(result.scalars().all())
    holdings_data = await latest_holding_views(db)
    holdings = holdings_data[0] if holdings_data is not None else []

    opt = await optimize_across_goals(
        goals,
        holdings,
        risk,
        today_ist(),
        get_settings().simulation_paths,
        total_budget=payload.total_budget,
        max_steps=payload.max_steps,
    )
    if opt is None:
        raise HTTPException(
            status_code=422,
            detail="Need at least one goal with a target value and date to optimize.",
        )
    return JointOptimizeRead.model_validate(opt)


@router.post("/{goal_id}/stress", response_model=StressTestRead)
async def stress_test(goal_id: int, db: DbSession, risk: RiskDep) -> StressTestRead:
    """Re-run the goal's Monte Carlo under a ladder of one-time market shocks."""
    goal = await _get_or_404(db, goal_id)
    holdings_data = await latest_holding_views(db)
    holdings = holdings_data[0] if holdings_data is not None else []

    result = await stress_test_goal(
        goal, holdings, risk, today_ist(), get_settings().simulation_paths
    )
    if result is None:
        raise HTTPException(
            status_code=422,
            detail="Goal needs a target value and target date to stress test.",
        )
    return StressTestRead.model_validate(result)
