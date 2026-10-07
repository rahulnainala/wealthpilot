"""Legacy sell-off plan constants shared across the backend.

The plan itself (status/progress computation) lives in the frontend's
``src/lib/exitPlan.ts`` — the backend only needs to *describe* it, in action
strings and AI prompts. Those descriptions used to hardcode the month, which
meant the date existed as prose in nine user-visible strings across both apps
and moving it silently left every label quoting the old one.

KEEP IN SYNC with ``frontend/src/lib/exitPlan.ts`` (``WINDOW_END``,
``SELL_THRESHOLD_PCT``). Two definitions is the floor without codegen; nine was
not. ``test_exit_plan_constants_match_frontend`` parses the TS file and fails if
they drift.

The values below are the demo investor's plan; a real install edits them here.
"""

from __future__ import annotations

from datetime import date

#: Sell each legacy name once it reaches this unrealized gain (%).
SELL_THRESHOLD_PCT = 10

#: Hard exit: anything still held at this date exits regardless of P&L.
EXIT_DEADLINE = date(2027, 6, 21)

#: Human label for EXIT_DEADLINE, e.g. "Jun 2027". Derive, never retype.
EXIT_DEADLINE_LABEL = EXIT_DEADLINE.strftime("%b %Y")

#: Proceeds routing, matching the monthly SIP split.
PROCEEDS_SPLIT_LABEL = "50/30/20 Travel/Vehicle/Emergency"
