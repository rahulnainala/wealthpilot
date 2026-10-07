"""Integration tests for the analytics endpoints (against the mock snapshot)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.fixture
async def with_snapshot(client: AsyncClient) -> AsyncClient:
    """A client with one refreshed snapshot to analyze."""
    resp = await client.post("/api/snapshots/refresh")
    assert resp.status_code == 200
    return client


async def test_issues_endpoint(with_snapshot: AsyncClient) -> None:
    resp = await with_snapshot.get("/api/analytics/issues")
    assert resp.status_code == 200
    codes = {i["code"] for i in resp.json()}
    assert "dividend_overweight" in codes
    # Growth must NOT fire — the snapshot's equity index funds ARE its growth
    # sleeve. See test_analytics_issues.test_equity_fund_counts_toward_growth.
    assert "growth_missing_third" not in codes
    # Most-severe first.
    assert resp.json()[0]["severity"] == "critical"


async def test_action_plan_endpoint(with_snapshot: AsyncClient) -> None:
    resp = await with_snapshot.get("/api/analytics/action-plan")
    assert resp.status_code == 200
    items = resp.json()
    assert items[0]["priority"] == 1
    assert all("action" in i and i["action"] for i in items)


async def test_mf_audit_endpoint(with_snapshot: AsyncClient) -> None:
    resp = await with_snapshot.get("/api/analytics/mf-audit")
    assert resp.status_code == 200
    rows = {r["isin"]: r for r in resp.json()}
    assert len(rows) == 6
    assert rows["INF769K01DM9"]["recommendation"] == "retire"
    assert rows["INF789F01XA0"]["annual_cost"] > 0


async def test_mf_audit_respects_er_override(with_snapshot: AsyncClient) -> None:
    await with_snapshot.put(
        "/api/settings/expense_ratios", json={"value": {"INF789F01XA0": 0.05}}
    )
    resp = await with_snapshot.get("/api/analytics/mf-audit")
    uti = next(r for r in resp.json() if r["isin"] == "INF789F01XA0")
    assert uti["expense_ratio"] == 0.05


async def test_goals_analysis_endpoint(with_snapshot: AsyncClient) -> None:
    # Seed the three goals via the CRUD API so analysis has something to work on.
    await with_snapshot.post(
        "/api/goals",
        json={
            "key": "fi",
            "name": "Financial Independence",
            "target_date": "2040-01-01",
            "assigned_buckets": ["dividend", "growth"],
            "assigned_isins": ["INF879O01027"],
        },
    )
    resp = await with_snapshot.get("/api/analytics/goals")
    assert resp.status_code == 200
    fi = next(g for g in resp.json() if g["key"] == "fi")
    assert fi["assigned_value"] > 0
    assert fi["simulation"] is None  # no risk-engine run yet (Phase 4B)


async def test_issues_404_without_snapshot(client: AsyncClient) -> None:
    resp = await client.get("/api/analytics/issues")
    assert resp.status_code == 404


async def test_projection_endpoint(with_snapshot: AsyncClient) -> None:
    resp = await with_snapshot.get("/api/analytics/projection?years=5")
    assert resp.status_code == 200
    points = resp.json()
    assert len(points) == 60  # 5 years x 12 months
    assert points[0]["month"] == 1
    assert points[-1]["month"] == 60
    assert points[-1]["p90"] >= points[-1]["p10"]


async def test_diversification_endpoint(with_snapshot: AsyncClient) -> None:
    resp = await with_snapshot.get("/api/analytics/diversification")
    assert resp.status_code == 200
    body = resp.json()
    assert body["holdings"] >= 2
    assert body["effective_holdings"] > 0
    assert isinstance(body["top_pairs"], list)


async def test_portfolio_risk_endpoint(with_snapshot: AsyncClient) -> None:
    resp = await with_snapshot.get("/api/analytics/portfolio-risk")
    assert resp.status_code == 200
    body = resp.json()
    assert body["confidence"] == 0.95
    assert body["var"] >= 0
    assert isinstance(body["contributions"], list)
    assert all("bucket" in c and "contribution" in c for c in body["contributions"])


def test_action_strings_do_not_contradict_the_written_plan() -> None:
    """The action plan must not argue with the owner's strategy doc.

    written plan binds two rules:
    the legacy basket exits on a +10%/Dec-2027 ladder, and NO new money goes
    into individual stocks. The generic remedies previously shipped told the
    owner to "trim the PSU-energy cluster" and to "average down" on a drawdown
    — the second is the exact inverse of the no-new-money rule, and it only
    ever surfaces when a position is already falling.
    """
    from app.domain.exit_plan import EXIT_DEADLINE_LABEL
    from app.routers.analytics import _ACTION_BY_CODE

    banned = ("average down", "buy the dip", "add to this position", "top up the position")
    for code, action in _ACTION_BY_CODE.items():
        lowered = action.lower()
        for phrase in banned:
            assert phrase not in lowered, f"{code} advises against the plan: {action!r}"

    # The two rows that describe the legacy basket must name the actual ladder,
    # not a generic trim — and must DERIVE the date, not retype it.
    label = EXIT_DEADLINE_LABEL.lower()
    assert label in _ACTION_BY_CODE["psu_energy_cluster"].lower()
    assert label in _ACTION_BY_CODE["position_drawdown"].lower()
    # Gold is out of scope for the sell-off and must not be told to trim.
    assert "hold" in _ACTION_BY_CODE["gold_overweight"].lower()


def test_no_action_string_hardcodes_a_month() -> None:
    """Action strings must derive the deadline, never retype it.

    The date used to live as prose in nine user-visible strings across both
    apps; moving it left every one of them quoting the old month.
    """
    from app.routers.analytics import _ACTION_BY_CODE

    months = ("jan", "feb", "mar", "apr", "may", "jun",
              "jul", "aug", "sep", "oct", "nov", "dec")
    from app.domain.exit_plan import EXIT_DEADLINE_LABEL

    derived = EXIT_DEADLINE_LABEL.lower()
    for code, action in _ACTION_BY_CODE.items():
        lowered = action.lower()
        for m in months:
            if m in lowered:
                # The only permitted month text is the derived label itself.
                assert derived in lowered, f"{code} hardcodes a month: {action!r}"


def test_exit_plan_constants_match_frontend() -> None:
    """Backend and frontend each define the plan once; they must agree.

    Two definitions is the floor without codegen. This parses the TS source so
    the pair cannot silently drift — which is the failure this whole change set
    exists to prevent.
    """
    import re
    from pathlib import Path

    from app.domain.exit_plan import EXIT_DEADLINE, SELL_THRESHOLD_PCT

    ts = Path(__file__).resolve().parents[2] / "frontend" / "src" / "lib" / "exitPlan.ts"
    src = ts.read_text()

    end = re.search(r'WINDOW_END = new Date\("(\d{4})-(\d{2})-(\d{2})', src)
    assert end, "WINDOW_END not found in exitPlan.ts"
    y, m, d = (int(g) for g in end.groups())
    assert (y, m, d) == (EXIT_DEADLINE.year, EXIT_DEADLINE.month, EXIT_DEADLINE.day)

    pct = re.search(r"SELL_THRESHOLD_PCT = (\d+)", src)
    assert pct and int(pct.group(1)) == SELL_THRESHOLD_PCT
