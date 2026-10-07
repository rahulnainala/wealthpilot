"""Portfolio issue-detection rules (pure).

Each rule inspects the current holdings + cash and, when triggered, emits an
:class:`Issue` carrying a severity, a human-readable message, and the relevant
rupee figure. Thresholds are module constants so they read as policy.
"""

from __future__ import annotations

from app.analytics.buckets import (
    Sleeve,
    invested_value,
    non_gold_invested,
    sleeve_for,
    sleeve_totals,
)
from app.analytics.models import (
    SEVERITY_ORDER,
    HoldingView,
    Issue,
    Severity,
    total_value,
)

# --- Thresholds (policy) -----------------------------------------------------
# Allocation thresholds are measured against the NON-GOLD invested base (the
# three-way growth/dividend/MF split), not against total portfolio value. Using
# `total` mixed gold and idle cash into the denominator, so the reported figure
# never matched the target the message quoted.
GROWTH_TARGET_PCT = 33.0  # the "third" the split is aiming at
GROWTH_MIN_PCT = 20.0     # critical only when materially below that third
DIVIDEND_MAX_PCT = 45.0
PSU_CLUSTER_MAX_PCT = 15.0
SINGLE_SYMBOL_MAX_PCT = 8.0
GOLD_MAX_PCT = 8.0
TINY_POSITION_RUPEES = 1_500.0
DRAWDOWN_PCT = -8.0
LOW_CASH_RUPEES = 500.0

PSU_ENERGY_CLUSTER: frozenset[str] = frozenset({"ONGC", "IOC", "BPCL", "COALINDIA"})
ELSS_ISINS: frozenset[str] = frozenset({"INF769K01DM9", "INF0R8F01026"})


def _pct(value: float, total: float) -> float:
    return round(value / total * 100, 2) if total else 0.0


def detect_issues(holdings: list[HoldingView], cash: float) -> list[Issue]:
    """Run every rule and return issues sorted most-severe first."""
    total = total_value(holdings, cash)
    issues: list[Issue] = []
    if total <= 0:
        return issues

    sleeves = sleeve_totals(holdings)
    growth = sleeves[Sleeve.GROWTH]
    dividend = sleeves[Sleeve.DIVIDEND]
    gold = sleeves[Sleeve.GOLD]
    invested = invested_value(holdings)
    non_gold = non_gold_invested(holdings)

    # 1. Missing growth "third".
    #    Reads the GROWTH SLEEVE, not the growth bucket: an equity index fund is
    #    growth exposure held in a fund wrapper. Counting only direct stocks
    #    reported ~8% growth for a portfolio that was ~44% equity growth.
    growth_pct = _pct(growth, non_gold)
    if non_gold > 0 and growth_pct < GROWTH_MIN_PCT:
        target_value = round(non_gold * GROWTH_TARGET_PCT / 100, 2)
        issues.append(
            Issue(
                code="growth_missing_third",
                severity=Severity.CRITICAL,
                title="Growth allocation too low",
                message=(
                    f"Growth is {growth_pct}% of your non-gold investments "
                    f"(\u20b9{growth:,.0f} of \u20b9{non_gold:,.0f}) \u2014 under the "
                    f"{GROWTH_MIN_PCT:.0f}% floor. A full third would be "
                    f"~\u20b9{target_value:,.0f}."
                ),
                amount=growth,
                pct_of_total=growth_pct,
            )
        )

    # 2. Dividend overweight.
    if non_gold > 0 and _pct(dividend, non_gold) > DIVIDEND_MAX_PCT:
        issues.append(
            Issue(
                code="dividend_overweight",
                severity=Severity.CRITICAL,
                title="Dividend bucket overweight",
                message=(
                    f"Dividend holdings are {_pct(dividend, non_gold)}% of your non-gold "
                    f"investments "
                    f"(over the {DIVIDEND_MAX_PCT:.0f}% ceiling)."
                ),
                amount=dividend,
                pct_of_total=_pct(dividend, non_gold),
            )
        )

    # 3. PSU / energy cluster concentration.
    cluster = [h for h in holdings if h.symbol.upper() in PSU_ENERGY_CLUSTER]
    cluster_value = round(sum(h.value for h in cluster), 2)
    if _pct(cluster_value, invested) > PSU_CLUSTER_MAX_PCT:
        issues.append(
            Issue(
                code="psu_energy_cluster",
                severity=Severity.WARNING,
                title="PSU-energy cluster concentration",
                message=(
                    f"ONGC/IOC/BPCL/COALINDIA together are {_pct(cluster_value, invested)}% "
                    "of the portfolio — correlated single-sector risk."
                ),
                amount=cluster_value,
                pct_of_total=_pct(cluster_value, invested),
                symbols=sorted(h.symbol for h in cluster),
            )
        )

    # 4. Single-symbol concentration (one issue per offending symbol).
    #    Gold is skipped: rule 8 already governs it with the SAME 8% threshold,
    #    so a single gold instrument crossing 8% used to raise two issues with
    #    identical numbers every time.
    for h in holdings:
        if sleeve_for(h.bucket, h.symbol) is Sleeve.GOLD:
            continue
        if _pct(h.value, invested) > SINGLE_SYMBOL_MAX_PCT:
            issues.append(
                Issue(
                    code="single_symbol_concentration",
                    severity=Severity.WARNING,
                    title=f"{h.symbol} over-concentrated",
                    message=(
                        f"{h.symbol} is {_pct(h.value, invested)}% of your invested value "
                        f"(over {SINGLE_SYMBOL_MAX_PCT:.0f}%)."
                    ),
                    amount=h.value,
                    pct_of_total=_pct(h.value, invested),
                    symbols=[h.symbol],
                )
            )

    # 5. Positions too small to matter.
    #    Suppressed on small portfolios. TINY_POSITION_RUPEES is absolute while
    #    SINGLE_SYMBOL_MAX_PCT is relative; they cross once the 8% cap falls
    #    below \u20b91,500 (a total under \u20b918,750). Past that point EVERY holding
    #    trips one rule or the other and no allocation can satisfy both, so the
    #    advice would be noise rather than guidance.
    tiny_rule_applies = invested * SINGLE_SYMBOL_MAX_PCT / 100 > TINY_POSITION_RUPEES
    for h in holdings if tiny_rule_applies else []:
        if 0 < h.value < TINY_POSITION_RUPEES:
            issues.append(
                Issue(
                    code="position_too_small",
                    severity=Severity.WARNING,
                    title=f"{h.symbol} too small to matter",
                    message=(
                        f"{h.symbol} is worth ₹{h.value:,.0f} — below "
                        f"₹{TINY_POSITION_RUPEES:,.0f}; it barely moves the needle."
                    ),
                    amount=h.value,
                    symbols=[h.symbol],
                )
            )

    # 6. Position drawdown. INFO, not WARNING: a position being down is the
    #    market moving, not a defect in how the portfolio is built. Ranking it
    #    beside real allocation problems is what made the list cry wolf.
    for h in holdings:
        if h.pnl_pct < DRAWDOWN_PCT:
            issues.append(
                Issue(
                    code="position_drawdown",
                    severity=Severity.INFO,
                    title=f"{h.symbol} down {h.pnl_pct:.1f}%",
                    message=(
                        f"{h.symbol} is down {h.pnl_pct:.1f}% "
                        f"(₹{h.pnl:,.0f} unrealized)."
                    ),
                    amount=h.pnl,
                    symbols=[h.symbol],
                )
            )

    # 7. Low cash.
    if cash < LOW_CASH_RUPEES:
        issues.append(
            Issue(
                code="low_cash",
                severity=Severity.INFO,
                title="Low cash balance",
                message=f"Cash is ₹{cash:,.0f} — little dry powder for opportunities.",
                amount=cash,
            )
        )

    # 8. Gold overweight.
    if _pct(gold, invested) > GOLD_MAX_PCT:
        issues.append(
            Issue(
                code="gold_overweight",
                severity=Severity.INFO,
                title="Gold overweight",
                message=(
                    f"Gold is {_pct(gold, invested)}% of your invested value "
                    f"(over {GOLD_MAX_PCT:.0f}%)."
                ),
                amount=gold,
                pct_of_total=_pct(gold, invested),
            )
        )

    # 9. Duplicate 80C ELSS vehicles.
    held_elss = sorted({h.symbol for h in holdings} & ELSS_ISINS)
    if len(held_elss) == len(ELSS_ISINS):
        elss_value = round(
            sum(h.value for h in holdings if h.symbol in ELSS_ISINS), 2
        )
        issues.append(
            Issue(
                code="duplicate_elss",
                severity=Severity.WARNING,
                title="Duplicate 80C ELSS funds",
                message=(
                    "Two ELSS funds serve the same 80C purpose — consolidate as "
                    "3-year locks expire and redirect to Growth."
                ),
                amount=elss_value,
                symbols=held_elss,
            )
        )

    issues.sort(key=lambda i: SEVERITY_ORDER[i.severity])
    return issues
