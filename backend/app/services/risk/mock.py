"""In-process risk client used when the C++ gRPC engine isn't available.

Uses a closed-form normal approximation rather than a Monte Carlo simulation, so
it is deterministic and dependency-free — good enough for offline development and
tests. The real numbers come from the C++ engine via :mod:`grpc_client`.
"""

from __future__ import annotations

import math
import random
from dataclasses import replace

from app.services.risk.base import (
    BaseRiskClient,
    BucketRisk,
    CorrelatedPair,
    DiversificationAsset,
    DiversificationOutcome,
    GoalSimInputs,
    GoalSimOutcome,
    PortfolioRiskOutcome,
    ProjectionPoint,
    RetirementPlanInputs,
    RetirementPlanOutcome,
    RiskContribution,
    Sleeve,
)

# 10th/90th percentile z-scores of the standard normal.
_Z10 = 1.2815515594463707

# The retirement-plan simulation (unlike the rest of this client) is a real
# per-path Monte Carlo, not a closed-form approximation — depletion during
# drawdown is path-dependent and doesn't have a clean formula. A few hundred
# paths in pure Python is still fast (a few hundred thousand iterations) and
# plenty for offline dev/tests; the real numbers come from the C++ engine.
_MOCK_RETIREMENT_PATHS = 400


def _percentile(sorted_values: list[float], q: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    rank = q * (len(sorted_values) - 1)
    lower = math.floor(rank)
    upper = math.ceil(rank)
    frac = rank - lower
    return sorted_values[lower] + frac * (sorted_values[upper] - sorted_values[lower])


def _schedule_at(schedule: list[float], month: int, fallback: float) -> float:
    """Empty -> fallback; shorter than the phase -> holds its last value."""
    if not schedule:
        return fallback
    if month < 0:
        return schedule[0]
    if month < len(schedule):
        return schedule[month]
    return schedule[-1]


def _contribution_weights(sleeves: list[Sleeve]) -> list[float]:
    total = sum(s.value for s in sleeves)
    if total > 0:
        return [s.value / total for s in sleeves]
    if sleeves:
        return [1.0 / len(sleeves) for _ in sleeves]
    return []


def _phi(x: float) -> float:
    """Standard normal CDF."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _shocked(sleeve: Sleeve, shock: float) -> Sleeve:
    """Apply a one-time shock to a sleeve, scaled by its volatility beta."""
    beta = min(1.0, sleeve.annual_return_volatility / 0.18)
    return replace(sleeve, value=max(0.0, sleeve.value * (1.0 + shock * beta)))


class MockRiskEngineClient(BaseRiskClient):
    async def health(self) -> bool:
        return True

    async def simulate_goal(self, inputs: GoalSimInputs) -> GoalSimOutcome:
        years = max(0.0, inputs.months_remaining / 12.0)

        # One-time market shock at t=0, beta-scaled by each sleeve's volatility
        # (mirrors the C++ engine: equity takes the full hit, near-cash barely moves).
        if inputs.initial_shock != 0.0:
            inputs = replace(
                inputs, sleeves=[_shocked(s, inputs.initial_shock) for s in inputs.sleeves]
            )

        total_start = sum(s.value for s in inputs.sleeves)

        # Value-weighted blended assumptions (equal-weight if no starting money).
        if total_start > 0:
            mean = sum(s.value * s.annual_return_mean for s in inputs.sleeves) / total_start
            vol = sum(s.value * s.annual_return_volatility for s in inputs.sleeves) / total_start
        elif inputs.sleeves:
            mean = sum(s.annual_return_mean for s in inputs.sleeves) / len(inputs.sleeves)
            vol = sum(s.annual_return_volatility for s in inputs.sleeves) / len(inputs.sleeves)
        else:
            mean = vol = 0.0

        # Future value of current holdings (per-sleeve growth) + contributions.
        holdings_fv = sum(s.value * math.exp(s.annual_return_mean * years) for s in inputs.sleeves)
        monthly_rate = mean / 12.0
        n = inputs.months_remaining
        if abs(monthly_rate) < 1e-9:
            contrib_fv = inputs.monthly_contribution * n
        else:
            contrib_fv = inputs.monthly_contribution * ((1 + monthly_rate) ** n - 1) / monthly_rate
        ending_mean = holdings_fv + contrib_fv

        ending_std = ending_mean * vol * math.sqrt(years) if years > 0 else 0.0

        if ending_std <= 0:
            probability = 1.0 if ending_mean >= inputs.target_value else 0.0
        else:
            probability = 1.0 - _phi((inputs.target_value - ending_mean) / ending_std)

        p10 = max(0.0, ending_mean - _Z10 * ending_std)
        p90 = ending_mean + _Z10 * ending_std
        return GoalSimOutcome(
            probability_of_success=round(probability, 4),
            median_ending_value=round(ending_mean, 2),
            p10_value=round(p10, 2),
            p90_value=round(p90, 2),
        )

    async def compute_portfolio_risk(
        self, buckets: list[BucketRisk], confidence: float = 0.95
    ) -> PortfolioRiskOutcome:
        total = sum(b.value for b in buckets)
        periods = min((len(b.returns) for b in buckets if b.returns), default=0)
        if total <= 0 or periods == 0:
            return PortfolioRiskOutcome(var=0.0, cvar=0.0, contributions=[])

        weights = {b.bucket: b.value / total for b in buckets}
        portfolio = [
            sum(weights[b.bucket] * b.returns[t] for b in buckets) for t in range(periods)
        ]

        # Annualized vol + max drawdown need the chronological series.
        mean = sum(portfolio) / periods
        periodic_sd = math.sqrt(sum((r - mean) ** 2 for r in portfolio) / periods)
        annual_volatility = periodic_sd * math.sqrt(252.0)
        wealth = peak = 1.0
        max_drawdown = 0.0
        for r in portfolio:
            wealth *= 1.0 + r
            peak = max(peak, wealth)
            if peak > 0.0:
                max_drawdown = max(max_drawdown, 1.0 - wealth / peak)

        ordered = sorted(portfolio)
        alpha = 1.0 - confidence
        idx = max(0, min(periods - 1, int(alpha * periods)))
        q = ordered[idx]
        tail = [r for r in ordered if r <= q] or [ordered[0]]
        cvar = -sum(tail) / len(tail) * total
        var = -q * total

        contributions = [
            RiskContribution(bucket=b.bucket, contribution=round(var * weights[b.bucket], 2))
            for b in buckets
        ]
        return PortfolioRiskOutcome(
            var=round(var, 2),
            cvar=round(cvar, 2),
            annual_volatility=annual_volatility,
            max_drawdown=max_drawdown,
            contributions=contributions,
        )

    async def simulate_portfolio_projection(
        self,
        sleeves: list[Sleeve],
        monthly_contribution: float,
        months: int,
        num_paths: int = 10_000,
        seed: int = 0,
    ) -> list[ProjectionPoint]:
        total = sum(s.value for s in sleeves)
        if total > 0:
            mean = sum(s.value * s.annual_return_mean for s in sleeves) / total
            vol = sum(s.value * s.annual_return_volatility for s in sleeves) / total
        elif sleeves:
            mean = sum(s.annual_return_mean for s in sleeves) / len(sleeves)
            vol = sum(s.annual_return_volatility for s in sleeves) / len(sleeves)
        else:
            mean = vol = 0.0

        monthly_rate = mean / 12.0
        points: list[ProjectionPoint] = []
        for m in range(1, months + 1):
            years = m / 12.0
            holdings_fv = sum(
                s.value * math.exp(s.annual_return_mean * years) for s in sleeves
            )
            if abs(monthly_rate) < 1e-9:
                contrib_fv = monthly_contribution * m
            else:
                contrib_fv = (
                    monthly_contribution * ((1 + monthly_rate) ** m - 1) / monthly_rate
                )
            mean_value = holdings_fv + contrib_fv
            std = mean_value * vol * math.sqrt(years) if years > 0 else 0.0
            points.append(
                ProjectionPoint(
                    month=m,
                    p10=round(max(0.0, mean_value - _Z10 * std), 2),
                    median=round(mean_value, 2),
                    p90=round(mean_value + _Z10 * std, 2),
                )
            )
        return points

    async def compute_diversification(
        self, assets: list[DiversificationAsset]
    ) -> DiversificationOutcome:
        n = len(assets)
        wsum = sum(a.weight for a in assets) or 1.0
        w = [a.weight / wsum for a in assets]
        eff = 1.0 / sum(x * x for x in w) if any(w) else float(n)

        series = [a.returns for a in assets]
        periods = min((len(s) for s in series if s), default=0)
        if n < 2 or periods < 2:
            return DiversificationOutcome(0.0, 1.0, round(eff, 2), n, [])

        means = [sum(s[:periods]) / periods for s in series]
        sds = [
            (sum((s[t] - means[i]) ** 2 for t in range(periods)) / periods) ** 0.5
            for i, s in enumerate(series)
        ]

        pairs: list[CorrelatedPair] = []
        weighted_corr = weight_pairs = 0.0
        for i in range(n):
            for j in range(i + 1, n):
                cov = sum(
                    (series[i][t] - means[i]) * (series[j][t] - means[j])
                    for t in range(periods)
                ) / periods
                denom = sds[i] * sds[j]
                corr = cov / denom if denom > 0 else 0.0
                pw = w[i] * w[j]
                weighted_corr += pw * corr
                weight_pairs += pw
                pairs.append(CorrelatedPair(assets[i].label, assets[j].label, round(corr, 3)))
        avg_corr = weighted_corr / weight_pairs if weight_pairs > 0 else 0.0

        pret = [sum(w[i] * series[i][t] for i in range(n)) for t in range(periods)]
        pmean = sum(pret) / periods
        psd = (sum((r - pmean) ** 2 for r in pret) / periods) ** 0.5
        weighted_avg_vol = sum(w[i] * sds[i] for i in range(n))
        ratio = weighted_avg_vol / psd if psd > 0 else 1.0

        pairs.sort(key=lambda p: p.correlation, reverse=True)
        return DiversificationOutcome(
            round(avg_corr, 3), round(ratio, 3), round(eff, 2), n, pairs[:5]
        )

    async def simulate_retirement_plan(
        self, inputs: RetirementPlanInputs
    ) -> RetirementPlanOutcome:
        accum = max(0, inputs.accumulation_months)
        draw = max(0, inputs.drawdown_months)
        total_months = accum + draw
        if total_months == 0 or not inputs.sleeves:
            return RetirementPlanOutcome(
                probability_of_success=0.0,
                median_corpus=0.0,
                p10_corpus=0.0,
                p90_corpus=0.0,
                depletion_probability=0.0,
                median_depletion_month=-1.0,
                median_terminal_value=0.0,
                bands=[],
            )

        paths = inputs.num_paths if inputs.num_paths > 0 else _MOCK_RETIREMENT_PATHS
        weights = _contribution_weights(inputs.sleeves)
        rng = random.Random(inputs.seed or None)

        # Sample the fan yearly (month 0 included) rather than monthly.
        band_months = [0]
        m = 12
        while m <= total_months:
            band_months.append(m)
            m += 12
        if band_months[-1] != total_months:
            band_months.append(total_months)

        banded = [[0.0] * paths for _ in band_months]
        corpus_at_retirement = [0.0] * paths
        terminal = [0.0] * paths
        depletion_months: list[float] = []

        for p in range(paths):
            values = [s.value for s in inputs.sleeves]
            next_band = 0

            def record(month_done: int) -> None:
                nonlocal next_band
                while next_band < len(band_months) and band_months[next_band] == month_done:
                    banded[next_band][p] = sum(values)
                    next_band += 1

            record(0)
            if accum == 0:
                corpus_at_retirement[p] = sum(values)

            path_depletion = -1.0
            for month in range(total_months):
                accumulating = month < accum
                total_before = sum(values) if not accumulating else 0.0
                withdrawal = (
                    0.0
                    if accumulating
                    else min(total_before, _schedule_at(inputs.withdrawal_schedule, month - accum, 0.0))
                )
                contribution = (
                    _schedule_at(inputs.contribution_schedule, month, inputs.monthly_contribution)
                    if accumulating
                    else 0.0
                )

                for i, sleeve in enumerate(inputs.sleeves):
                    monthly_mean = sleeve.annual_return_mean / 12.0
                    monthly_vol = sleeve.annual_return_volatility / math.sqrt(12.0)
                    shock = rng.gauss(0.0, 1.0) if monthly_vol > 0 else 0.0
                    growth = math.exp(
                        (monthly_mean - 0.5 * monthly_vol * monthly_vol) + monthly_vol * shock
                    )
                    share = values[i] / total_before if total_before > 0 else weights[i]
                    values[i] = values[i] * growth + contribution * weights[i] - withdrawal * share
                    if values[i] < 0.0:
                        values[i] = 0.0

                if month + 1 == accum:
                    corpus_at_retirement[p] = sum(values)
                if not accumulating and path_depletion < 0.0:
                    # A corpus this small can't fund another month — call it
                    # depleted rather than letting a rounding crumb compound
                    # back to life.
                    if sum(values) <= 1.0:
                        path_depletion = float(month - accum + 1)
                record(month + 1)

            terminal[p] = sum(values)
            if path_depletion >= 0.0:
                depletion_months.append(path_depletion)

        hits = sum(1 for v in corpus_at_retirement if v >= inputs.target_value)
        sorted_corpus = sorted(corpus_at_retirement)
        sorted_terminal = sorted(terminal)
        depletion_months.sort()

        bands = [
            ProjectionPoint(
                month=month,
                p10=round(_percentile(sorted(col), 0.10), 2),
                median=round(_percentile(sorted(col), 0.50), 2),
                p90=round(_percentile(sorted(col), 0.90), 2),
            )
            for month, col in zip(band_months, banded)
        ]

        return RetirementPlanOutcome(
            probability_of_success=round(hits / paths, 4),
            median_corpus=round(_percentile(sorted_corpus, 0.50), 2),
            p10_corpus=round(_percentile(sorted_corpus, 0.10), 2),
            p90_corpus=round(_percentile(sorted_corpus, 0.90), 2),
            depletion_probability=round(len(depletion_months) / paths, 4),
            median_depletion_month=(
                round(_percentile(depletion_months, 0.50), 1) if depletion_months else -1.0
            ),
            median_terminal_value=round(_percentile(sorted_terminal, 0.50), 2),
            bands=bands,
        )
