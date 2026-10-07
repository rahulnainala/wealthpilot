# Risk metrics used in WealthPilot

Value at Risk (VaR) at 95% confidence is the one-day loss the portfolio would
exceed only 5% of the time, computed historically from ~3 months of daily NSE
returns. Conditional VaR (CVaR / expected shortfall) is the average loss on
those worst 5% of days — always ≥ VaR and a better read on tail pain.

Annualized volatility scales the daily standard deviation of portfolio
returns by √252. For context: large-cap Indian equity typically runs 14–20%,
short-duration debt 1–3%, gold 12–18%. Max drawdown is the worst
peak-to-trough fall of the cumulative wealth index over the window — it
measures the pain of holding through the period, not a forecast.

Risk contributions decompose CVaR by bucket (Euler allocation): each bucket's
average return on the tail days times its value. They sum to portfolio CVaR,
so a bucket with a small weight but high tail-beta can still dominate risk.

The diversification ratio is weighted-average asset volatility divided by
portfolio volatility — 1.0 means no diversification benefit; >1.3 is healthy
for a mixed equity/debt/gold book. Effective holdings = 1 / HHI of weights:
how many *independent* bets the portfolio really contains. High pairwise
correlation (e.g. two oil-marketing PSUs at 0.9) collapses effective holdings
even when the ticker count looks diversified.
