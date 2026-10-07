# Indian market structure and trading mechanics

NSE and BSE are the exchanges; most liquidity is on NSE. Settlement is
T+1: sell on Monday, cash is withdrawable Tuesday. Delivery shares live in
your demat (CDSL/NSDL); Zerodha is the broker interface.

Zerodha order types: CNC (delivery — what a long-term portfolio uses), MIS
(intraday, auto-squared-off), GTT (good-till-triggered — a standing trigger
that places an order when price crosses a level; ideal for the +10% sell
thresholds in the exit plan since it works while you are not watching).
Limit orders protect against illiquid spreads; market orders on illiquid
names (small REITs) can slip several percent — always use limits there.

Circuit limits halt or band stocks: individual stocks have 5/10/20% daily
bands; indexes halt trading at −10/−15/−20%. Lower-circuit days can make
exits impossible — another reason position sizes matter.

Charges on delivery equity: 0.1% STT on sell, exchange charges, ~0.02%
stamp duty on buy, DP charge ₹13.5+GST per stock per sell day, zero
brokerage on delivery at Zerodha. Round-trip cost ≈ 0.15–0.2% — small, but
it means churning erodes returns.

Market hours 9:15–15:30 IST; pre-open auction 9:00–9:08 sets opening
prices. AMO (after-market orders) queue for the open.

Corporate actions: dividends (record date determines eligibility; price
drops ex-date), buybacks (tender via broker; gains tax-free to holder
post-2024 rules changed — verify current year), splits/bonuses (units
adjust, value unchanged), rights entitlements (trade or exercise before
expiry — REIT rights like BIRET-RR lapse worthless if ignored).

The portfolio's quote feed: Kite for holdings truth, Yahoo for history and
live NSE indices; illiquid names can print stale ticks, which the app
band-filters (sanePrice) before showing.
