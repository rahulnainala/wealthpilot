# WealthPilot AI Roadmap

Decided 2026-07-11. Each phase ships independently; UI work runs through
`/master-ui-orchestrator` (feature-build pipeline). Architecture principle:
**every number comes from the engine/DB; the model narrates, never invents.**

## Model strategy — local-first (no API key; Claude Pro ≠ API)

All AI runs locally on the 3070's Ollama (`OLLAMA_URL=http://<3070-lan-ip>:11434`).
The Anthropic path exists in code but is unused (no key).

| Role | Model (live) | Fallback |
|---|---|---|
| Daily brief, insights, chat | **`wealthpilot`** — our fine-tuned Qwen2.5-7B-Instruct QLoRA (live since 2026-07-12; `OLLAMA_MODEL=wealthpilot`) | `deepseek-r1:14b` (set OLLAMA_MODEL back; `<think>` stripped) or Anthropic API if a key is ever added |
| Embeddings for RAG | `nomic-embed-text` on 3070 (768-dim, free) | — |

Grounding is mandatory: local models declare tool capability but ignore tools
and hallucinate numbers, so chat **always injects precomputed context**
(`chat_service._gather_context`) and `keep_alive:-1`/`num_ctx 8192` are set on
every call. Backend probes `OLLAMA_URL` with a 2s timeout (same pattern as the
risk-engine health badge); reachable → serve; not → degrade gracefully.
`normalize_followups` cleans the model's FOLLOW-UPS trailer on every reply.

## RAG — local, on existing infra

- **Vector store: pgvector extension on the existing Postgres container.**
  No new service, survives restarts, SQL-joinable with snapshots.
- Corpus: daily snapshots (serialized deltas), issues history, goal-sim
  results, exit-plan events, MF audit notes, user notes/Notion exports
  dropped into `docs/knowledge/`.
- Ingestion: nightly scheduler job → chunk (per-document, ~500 tokens) →
  embed via 3070 when on (else queue; Redis list `wp:ai:embed-queue`).
- Retrieval feeds Phases 2–4 with "what happened before" context, e.g.
  "your VaR spiked like this on 2026-05-12 when energy fell 4%".
- **S3: optional backup only** (pg_dump + knowledge folder, lifecycle to
  Glacier). Not in the serving path — a personal app needs no cloud store.

## Phases

1. **Daily AI Brief** (Overview panel): `/api/ai/brief`, context compiled
   from snapshot+risk+diversification+issues+exit-plan; Redis-cached 24h,
   regenerated on snapshot refresh + 09:45 IST scheduler. Haiku/Ollama.
2. **Ask WealthPilot** (⌘K chat drawer): Sonnet tool-use over existing
   endpoints (holdings, risk, simulate(months,SIP,shock), exit plan);
   SSE streaming; RAG context injected.
3. **Proactive intelligence** — CORE BUILT 2026-07-11 (daily distillation into RAG via nightly job; news/sell-timing context remains): sell-timing context (news/earnings via web
   search) on Action Plan cards; AI-explained issues; EOD digest job.
4. **Goal-plan copilot** — BUILT 2026-07-11 (chat tools list_goals + simulate_goal with SIP/target/shock overrides through the C++ engine): NL what-ifs → simulation params → C++ engine →
   narrated trade-offs vs the The plan. Read-only, engine-cited numbers.
5. **RAG foundation** — BUILT 2026-07-11: pgvector (image pgvector/pgvector:pg16,
   extension auto-created on startup), `knowledge_chunks` table (768-dim
   nomic-embed vectors, nullable until embedded), `app/services/ai/rag.py`
   (idempotent folder ingestion → paragraph-packed ~500-token chunks →
   resumable embed pass → cosine retrieval). Endpoints: POST /api/ai/ingest,
   GET /api/ai/search?q=. **Corpus**: `docs/knowledge/finance/` (seeded:
   risk metrics, Indian tax & costs, goal-investing principles — drop any
   finance material here as .md and it's learned), `docs/knowledge/
   portfolio/` for distilled history/notes. Mounted ro into the backend.
6. **Continuous learning loop** — DATA PIPELINE BUILT 2026-07-11: every
   chat exchange is logged (chat_exchanges table); GET /api/ai/training-data
   exports chat-tuning JSONL. When ~1k good pairs exist: on the 3070, export
   -> unsloth LoRA on the local model -> `ollama create wealthpilot-r1 -f
   Modelfile` -> set OLLAMA_MODEL=wealthpilot-r1. Base loop — nightly scheduler job (20:30 IST,
   `run_nightly_learning`) re-ingests the knowledge folder and embeds
   pending chunks whenever the 3070 is reachable; content edits null their
   vectors so knowledge stays current. Phase 3 extends this to distill each
   day's snapshot/decisions into `docs/knowledge/portfolio/` (gitignored — personal) so the AI
   compounds understanding of THIS portfolio over time. LoRA (below) is the
   later, optional step: when the PC is on —
   nightly embed backlog, distill the day into knowledge notes, and
   accumulate chat Q&A pairs; once >1k good pairs exist, LoRA-tune the
   local 8B on them (weekly, unsloth) so the local model learns *this*
   portfolio's vocabulary. Honest note: value comes mostly from RAG +
   accumulated notes; fine-tuning is a later optimization, not the start.

## Env additions (compose)

```
ANTHROPIC_API_KEY=...          # root .env (gitignored)
OLLAMA_URL=http://<3070>:11434 # optional; absent = cloud-only
AI_BRIEF_ENABLED=true
```

## Build order

1 → 5 → 2 → 3 → 4 → 6. Phase 1 first session: backend endpoint + provider
abstraction (anthropic|ollama behind one interface, health-probed) + brief
panel via /feature-build.

## Built 2026-07-11 (evening round)
Streaming chat (SSE /api/ai/chat/stream, think-phase tracking), delta-aware
brief (+?refresh=true), /api/ai/status + AI Systems panel, AskAI seeded
questions across Issues/ActionPlan/Goals/Risk/Diversification, day-change
Overview, Issues fix-routing, goal-target reference lines on projection.
Next: news/earnings context, weekly AI report page, voice input,
similar-past-days retrieval, LoRA at >=1k pairs.

## Built 2026-07-12 — "Pilot" (the AI feels alive)
Pilot persona across brief/chat/insights; conversations persist
(GET /api/ai/chat/history preloads the sheet); screen-context injected
into every prompt; FOLLOW-UPS chips parsed from each reply; AI Insights
(ai_insights table) regenerated on each learning run and shown as
dismissible chips on Overview — Pilot speaks first.

## Built 2026-07-12 — Finance-complete corpus + focused dashboards
Knowledge library grown to 13 docs (equity/index, MF mechanics, debt &
arbitrage, REITs/gold, market structure & Zerodha mechanics, insurance/
Phase 0, FI math, behavioral finance, drawdown history, glossary, + 3
seeds) — 16/16 chunks embedded; semantic probes route correctly. IA split
to 12 tabs in 4 groups (MONITOR/PLAN/AUDIT/SYSTEM): new Holdings, Risk,
and AI tabs (knowledge-search UI + recent conversations); Overview is a
lean cockpit.

## Built 2026-07-12 — custom-model pipeline
ai-training/ kit (export.sh -> train.jsonl, train_lora.py QLoRA on
Qwen2.5-7B-4bit for the 3070's 8GB, Modelfile -> `ollama create
wealthpilot`); /api/ai/status detects the wealthpilot model; AI tab
Custom Model panel tracks pairs/1000, exports data, and shows install
state. Switch via OLLAMA_MODEL=wealthpilot when trained.

## Built 2026-07-12 — all-Postgres stack + user knowledge notes
Redis removed: PgTTLCache (cache_entries) serves Kite/Yahoo/brief caches,
restart-proof (brief 0.086s after restart). Hash-randomization bugs fixed
(stable sha256 cache keys, crc32 synthetic seeds — VaR restart-stable).
Save-to-knowledge on Pilot replies -> user-notes/* embedded immediately;
RAG at 17/17. Stack: postgres + backend + frontend + risk-engine only.

## Built 2026-07-12 (late) — custom model LIVE + dataset hygiene
`wealthpilot` fine-tune trained on the 3070 (unsloth QLoRA, Qwen2.5-7B-4bit,
~1-2h) and serving: `OLLAMA_MODEL=wealthpilot`, `/api/ai/status` →
`custom_model_present: true`, Learn stepper at ③ FLY. Smoke-tested grounded
(cited real 18.49% PSU-energy concentration). FOLLOW-UPS artifact fixed at
both layers: runtime `normalize_followups` on all 3 Ollama paths + streaming
`final` SSE event (39ee099); training dataset cleaned at source
(`scripts/clean_training_pairs.py`, 1004→993 pairs, scaffold-free, idempotent
— 76c2634) so the next retrain learns clean format natively. Windows 3070
pulls clean data from `/api/ai/training-data` on the next `auto_train.py` run.

---

# Road ahead (Phase 7+) — from reactive answers to a proactive copilot

The AI foundation is complete: grounded brief, chat, insights, RAG memory,
nightly learning, and a live custom model. The theme going forward is **Pilot
acts before you ask** — watching the plan and telling you when to move. Every
number still comes from the engine/DB; the model narrates. Ordered by value.

**Phase 7 — Proactive watch & alert — BUILT 2026-07-12 (`b767307`).**
`services/ai/watch.py` evaluates rule-based conditions over computed state:
+10% sell-threshold crossings + the approaching band, single-name
concentration (≥12%), correlated pairs (≥0.6), 3-month drawdown beyond −15%,
worst goal below 50% success. Alerts persist as typed `AiInsight`s
(severity action|watch|info, `source`, `alert_key`; migration `e5f6a7b8c9d0`);
a dismissed alert stays hidden until its condition clears. Generation writes
watch alerts + model observations; the morning brief opens on active alerts
(cache key folds in alert state). `PilotInsights` renders per-severity. Verified
live: goal-off-track + 17.8% concentration + BPCL~IOC 0.93 fired.
- *Helps:* you stop watching the market daily — Pilot tells you the moment a
  legacy stock becomes sellable or a goal drifts off track.
- *Next within 7:* push notifications (browser/email) so alerts reach you
  when the app is closed.

**Phase 8 — Decision context on sell candidates — BUILT (`89a5539`).**
`services/ai/news.py` pulls recent headlines from Google News' free RSS (no API
key), cached 6h, degrading to empty when down. `GET /api/ai/news?query=` + a
`get_news` chat tool; each Action Plan sell candidate has a Newspaper toggle
listing headlines inline. *Helps:* "you can sell" → "whether to pull the
trigger now." Headlines are context, not advice.

**Phase 9 — Weekly written review — BUILT (`4ac8c08`).**
`services/ai/weekly_review.py` writes a 3-part review (this week vs week-ago
distilled note, sell plan & goals, one action), folds in watch alerts, cached
7 days. `GET /api/ai/weekly-review`, Sunday 07:30 IST cron pre-warm, Weekly
Review panel on the AI tab. (True email deferred — needs SMTP.)

**Phase 10 — Memory-powered analogues — BUILT (`914ce3a`).**
`rag.retrieve_daily_notes` + `find_similar_days` chat tool retrieve over the
`portfolio/daily-*` distilled notes ("your VaR looked like 2026-05-12").
Richer as the nightly distillation accumulates days.

**Phase 11 — Model quality loop — BUILT (`7f66dd3`).**
`training_state.py` + `/api/ai/status` (`pairs_since_train`,
`retrain_recommended` ≥150) + `POST /api/ai/mark-trained`; Learn-tab
readiness chip. `scripts/eval_models.py` A/B-scores wealthpilot vs a base on a
fixed question set (grounding/clean-trailer/followups/length).

**Phase 12 — Action drafting (human-in-loop) — BUILT (`c812ebe`).**
`services/ai/order_draft.py` drafts (never places) a GTT sell: qty, +10%
trigger, est. proceeds, 50/30/20 routing. `GET /api/ai/order-draft?symbol=` +
`draft_sell_order` chat tool + a Receipt button per sell candidate. Every draft
says review & place it yourself — Pilot never executes.

**Cross-cutting — remote access.** Public `rahulnainala.com` deploy
(Tailscale already in place) needs **auth added first** (app has none). Then
EC2 + Caddy; the AI reaches you anywhere. Separate track from the above.

Guardrails unchanged: read-only, engine-cited numbers, local-only, graceful
degradation when the 3070 is off. LoRA retrains stay on the organic-growth
schedule (don't chase raw pair count — quality/diversity over 10k dupes).

---

# Second-generation roadmap (Phase 13+) — advanced

Owner-selected 14 features (2026-07-12), sequenced into 4 waves; shipping
incrementally like 7–12. Full plan: `~/.claude/plans/breezy-rolling-rabbit.md`.

**Wave A — trust & delivery — BUILT.**
- Phase 13 · Confidence & staleness flags (`cb64343`) — `data_health.py`,
  `/api/ai/data-health`, chat staleness banner.
- Phase 14 · Citations + hybrid RAG (`ff96c07`) — `rag.hybrid_retrieve` (vector
  + keyword; works with the 3070 off), `[source]` citations in chat.
- Phase 15 · Push + PWA (`cbe80e9`) — pywebpush/VAPID, `push_subscriptions`,
  `push.py`, `/vapid-key`,`/subscribe`,`/test-push`; nightly pushes new action
  alerts; `manifest.webmanifest` + `sw.js` + `PushToggle` (installable app).

**Wave B — deeper reasoning — BUILT.**
- Phase 16 · Anomaly detection (`ec156ef`) — `anomaly.py` z-scores daily value
  moves vs the portfolio's own history → `anomaly:value` watch alert.
- Phase 17 · News sentiment (`f8627e1`) — `sentiment.py` bull/bear lexicon
  scores headlines; mood badge + dots on the Action Plan; `get_news` leads with mood.
- Phase 18 · Agentic planning (`9305186`) — `required_sip` tool + 8 tool rounds
  + plan-then-synthesize prompt; chains `list_goals → required_sip` per goal.
- Phase 19 · Optimization (`9880b99`) — `optimize.py` inverse-volatility risk
  parity (Python, reusing the goal engine's assumptions — not a C++ RPC);
  `/api/ai/optimize` + `optimize_portfolio` tool + Risk-tab Optimize panel.
**Wave C — money & tax — BUILT.**
- Phase 20 · Tax-aware sell plan (`13ea7e1`) — `tax.py` (LTCG 12.5%/₹1.25L,
  STCG 20%); order drafts carry gain + est. tax; `/api/ai/tax-summary` +
  `tax_impact` tool with harvest candidates. Defaults to LTCG (no buy-date), labelled.
- Phase 21 · Benchmark vs NIFTY (`dd68113`) — `benchmark.py` chains portfolio
  vs ^NSEI daily returns; `/api/ai/benchmark` + tool + Risk-tab panel.
- Phase 22 · Monthly PDF (`e5a8627`) — `report.py` via fpdf2; `/api/ai/monthly-report`
  + AI-tab download.
- Phase 23 · Statement ingestion (`c16a3f5`) — `statement_ingest.py` (pypdf,
  encrypted CAS) → RAG; `POST /api/ai/upload-statement` + AI-tab uploader.

**Wave D — model quality — BUILT.**
- Phase 24 · Eval dashboard (`3c1773f`) — `eval.py` shared scorer, `model_evals`
  table, `POST /run-eval` (background) + `GET /evals` + Learn-tab Model Quality
  card. First run: wealthpilot 21/24.
- Phase 25 · RAG-grounded fine-tune (`cff88a1`) — training-data export prefixes
  each example with the grounding system prompt (`[system,user,assistant]`).

**All 14 advanced features shipped.** Cross-cutting (separate track): public
`rahulnainala.com` deploy — needs auth first.

---

# Third-generation roadmap (Phase 26+)

Owner-selected 13 features (2026-07-12); plan in `~/.claude/plans/breezy-rolling-rabbit.md`.

**Wave E — interaction & autonomy foundation — BUILT.**
- 26 · What-if sliders (`6095f39`) — `WhatIfSliders`, live debounced `/goals/{id}/simulate`.
- 27 · NL→chart (`a371f7e`) — `chart_spec.py`, `/api/ai/chart`, `make_chart` tool emitting
  `[[chart:KIND]]`, `InlineChart` renders it in chat.
- 28 · Nightly action agent (`09a3170`) — `action_agent.py` chains watch→optimize→tax into
  a ranked plan (settings KV), `/daily-plan`(+refresh), nightly push, Today's Plan panel.

**Wave F — autonomy, advanced — BUILT.**
- 29 · Multi-agent critique (`4ea9927`) — `critique.py` risk-skeptic pass, `POST /critique`,
  Devil's-advocate button.
- 30 · Auto-retrain A/B gate (`2975d16`) — `ab_gate.py` evals live vs base + keep/revert rec
  (`/ab-eval`,`/ab-result`, Learn card). Fixed latent bug: `eval.run_eval` restores the live
  `ollama_model`.

**Wave G — deeper finance — BUILT.**
- 31 · FI/SWR (`cf54312`) — `fi.py` whole-portfolio MC + safe-withdrawal; new **Retirement** tab.
- 32 · Sector stress lab (`e3319a6`) — `stress.py` differentiated shocks; Risk-tab panel.
- 33 · Portfolio X-ray (`884bb48`) — `xray.py` asset-class look-through; Holdings panel.
- 34 · Dividend forecast (`86f5fa7`) — `dividends.py`; new **Income** tab.

**Wave H — memory/signals — BUILT.**
- 35 · Decision journal (`8d87227`) — `decisions` table + RAG ingest; new **Journal** tab.
- 36 · Macro dashboard (`02f8a92`) — `macro.py` INR/crude/NIFTY/VIX; new **Macro** tab.
- 37 · Time-travel (`fdb15e3`) — `timetravel.py` snapshot-as-of; Trends date slider.
- 38 · Earnings calendar (`3c1fbe5`) — `earnings.py` Yahoo quoteSummary + crumb handshake; Macro panel.

**All 13 third-gen features shipped (Phases 26–38).** Nav grew to 16 tabs across
Monitor/Plan/Audit/System; chat now has ~21 tools. Cross-cutting (separate
track): public `rahulnainala.com` deploy — needs auth first.

---

# Fourth-generation roadmap (Phase 39+) — execution, multimodal, full wealth, platform

Owner-selected 16 features (2026-07-13); plan in `~/.claude/plans/breezy-rolling-rabbit.md`.
This generation deliberately relaxes "read-only" for **execution** — behind
**auth + explicit confirmation + audit logging**, never silent — and widens scope
beyond Zerodha. Sequenced safety-and-dependency first.

**Pre-req — chat + IA fix — BUILT (`b55d759`).** Chat typing focus-steal fixed
(`ui/sheet.tsx` onClose ref); Monitor/Plan consolidated 16→14 tabs.

**Wave I — foundation & reliability — BUILT.**
- 39 · Kite auto-reconnect (`35a57e3`) — persist/refresh token, stale-session marking,
  401 handler; kills the refresh-502s.
- 40 · App-level auth (`6459c1e`) — single-user login; Fernet session tokens (no new deps),
  `_auth_gate` middleware, `require_auth` on every write/execution endpoint, `AuthGate` UI.
- 41 · Public deploy artifacts (`c549c12`) — Caddy same-origin reverse proxy + prod compose
  + runbook (`docs/DEPLOYMENT.md`); frontend build ARG `NEXT_PUBLIC_API_BASE_URL`.

**Wave J — execution (gated behind Wave I) — BUILT.**
- 42 · Guarded GTT execution (`86d4cb8`) — `execution.py` `execute_gtt_sell` with
  **dry-run default + confirm-gate + audit-log + `auth_enabled()` guard**; real placement
  is BLOCKED unless secured mode. `order_audit` table (`c9d0e1f2a3b4`).
- 43 · Basket rebalance preview (`bcee92a`) — read-only reviewable basket of orders.
- 44 · Opt-in auto-execute (`8134c6d`) — +10% GTT auto-place, **off by default**, routed
  through the same guard + kill-switch (settings KV `execution.auto_gtt`).

**Wave K — AI models & multimodal — BUILT.**
- 45 · Multi-model routing (`80a4d26`) — `ai/routing.py` `pick_model` (heavy model for
  complex/agentic messages) wired into the chat payloads.
- 46 · Predictive signals (`bc5f53c`) — `ai/forecast.py` EWMA (RiskMetrics λ=0.94) vol
  forecast + momentum; `/api/ai/forecast`. Honest statistical, not a price oracle.
- 47 · Voice (`5d67bb2`) — browser Web Speech API (webkitSpeechRecognition + speechSynthesis,
  en-IN); mic + speak toggle in the chat drawer. No server model; degrades gracefully.
- 48 · Chart/screenshot vision (`a9ce49c`) — `ai/vision.py` llava on the 3070 via
  `/api/generate`; `POST /api/ai/vision`.

**Wave L — wealth scope — BUILT (52 is a spike).**
- 49 · Full net-worth tracker (`b561d2c`) — `external_asset` table (`d0e1f2a3b4c5`) +
  `/api/assets`; net worth = portfolio + manual assets; NetWorthPanel on Holdings.
- 50 · Watchlist + gap screener (`70c9044`) — `watchlist` table (`e1f2a3b4c5d6`) + CRUD +
  live quotes + gap screener; WatchlistPanel on Market.
- 51 · Options / hedging (`17ffdba`) — `ai/options.py` protective-put sizing (equity-like
  exposure from xray, NIFTY put lots + est premium); `/api/ai/hedge` + Risk-tab HedgePanel.
- 52 · **Account Aggregator — SPIKE ONLY, blocked on a TSP account.** Design scoped in
  `docs/AA_SPIKE.md`; not coded (India AA needs a registered FIU/TSP + public HTTPS webhook).

**Wave M — intelligence depth — BUILT.**
- 53 · Joint multi-goal optimizer (`27e44fb`) — `optimize_across_goals` splits one monthly
  budget across goals for the most probability per rupee (max expected goals met, not a
  degenerate max-min); `POST /api/goals/optimize` + JointOptimizePanel on Goals.
- 54 · Sell-rule backtest (`27e44fb`) — `ai/backtest.py` replays the +10% take-profit rule
  vs buy-and-hold on the legacy book over Yahoo history; `/api/ai/backtest` + Risk panel.
  (Assumes a hypothetical entry at the window start, labelled — not real cost basis.)
- 55 · Factor tilts (`27e44fb`) — `ai/factors.py` heuristic value/momentum/quality/size
  proxy decomposition, value-weighted; `/api/ai/factors` + Risk panel. Labelled a proxy,
  not a regression factor model.

**15 of 16 fourth-gen features shipped (Phases 39–55); Phase 52 is a documented
spike pending an AA provider account.** Execution stays permanently guarded: real
orders are blocked unless secured mode — never tested against the live account.

---

## Wave N — correctness & consistency pass (2026-07-19/20)

Not new features. A sweep of all 15 tabs after the retirement/sell-off decisions,
which surfaced a set of numbers that were quietly wrong. Recorded here because
several were decision-relevant, not cosmetic.

**Scheduler / data integrity**
- Daily snapshots were being **dropped**, not delayed: the host sleeps past
  `misfire_grace_time` and APScheduler discards the run (real gaps 07-09, 07-15,
  07-16). Added `run_startup_catchup()` — on boot, backfill today's snapshot if
  missing — and widened the grace windows. `backend/tests/test_scheduler.py`.
- `/api/snapshots/history` now returns **one snapshot per IST day** (latest OK).
  Manual refreshes had some days holding 6–9 rows and others none, skewing trend
  charts and Overview's day-change baseline.
- `ist_date()` (`analytics_service`) — SQLite drops tzinfo, and a naive datetime
  through `.astimezone()` is read as system-local, shifting the calendar date.
  On an IST machine it only misbehaves between UTC-midnight and IST-midnight, so
  it hid ~77% of the day. Frontend mirror: `istDateKey()` in `lib/format`.

**Retirement (Phase 31 reworked)**
- Inflation-aware, floored at 6%. The target slider reads as *today's* purchasing
  power and is inflated to the nominal corpus actually needed (₹1.5Cr by 2040 =
  ₹3.2Cr nominal); every output shows both framings. Engine stays nominal.
- `post_selloff` reclassifies the dividend sleeve as equity — the allocation the
  +10%/Dec-2027 plan actually ends at (~88% equity).
- Required-SIP bisection so the page answers "what would it take" instead of
  reporting 0%. `backend/tests/test_fi.py`.

**Cross-tab consistency**
- Basket's legacy panel now derives exit status from `lib/exitPlan` — the same
  module Action Plan executes from — and unassigned *mutual funds* are split out
  of the sell list (it had Zerodha Nifty 50 queued for sale, the opposite of the
  plan). `monthsLeftLabel()` / `isSellNow()` centralised after the two tabs
  disagreed on months left (18 vs 17) and on whether `deadline` counts as ready.
- Goal probabilities could be **stale**: the headline read a cached
  `goal_simulation` row, so after any goal change it showed the old number until
  a reload — measured 98.5% cached against a true 4%. Fresh runs now lift to tab
  level and feed both cards and the summary's on-track count.
- FI dropped from the Goals tab (it's a projection, not a dated milestone —
  Retirement owns it); the goal record stays for Basket's 10% sleeve.
- SIP budget control on Basket (₹10k–₹2L) with live funding routes; preview-only
  so exploring can't re-rate goals.

**Display honesty**
- `sharePct()` — a 0.3%-saved goal rendered as "0%" next to a 99% probability.
- `pct()` no longer signs a rounded-away zero ("-0.00%" read as a loss).
- FlightStrip's VS readout was showing **lifetime return** under a
  "change vs last snapshot" label when no prior snapshot existed; now nullable.
- `dateOnly()` pins Asia/Kolkata (the owner may live abroad before these goals
  mature); Journal/Learn dated rows off the raw UTC string, so an entry logged
  at 00:17 IST displayed a day early. Added `istTime()`.
- Issues: the two *critical* codes matched no fix-link route, so the most severe
  rows were the only ones with no next step. All classes now route.

**Resilience**
- The nightly job pre-generates the morning brief, so the one AI surface without
  a stored fallback survives a sleeping 3070. See `docs/DEPLOYMENT.md` for the full
  offline matrix — the GPU only needs the 20:30 IST window.

### UI pass (same sweep)

- **Live order placement got a real confirm dialog.** Placing a GTT is the only
  action that touches the Zerodha account, and it was gated by two `text-2xs`
  inline links — no dialog semantics, no focus trap, no Escape, and the confirm
  sat one stray click from the trigger. `ui/confirm-dialog.tsx` follows
  `sheet.tsx`'s existing behaviour discipline but uses `role="alertdialog"` and
  puts initial focus on **Cancel**, so a stray Enter backs out rather than
  placing an order. It restates the exact order (side/qty/symbol/trigger)
  instead of asking the user to trust what's behind the overlay.
- **Goals decluttered.** Each card rendered its What-If panel permanently
  expanded while the two panels beside it were collapsed disclosures — the
  exploratory tool was the loudest thing on the card and fired a simulate call
  per goal on load. Now a peer toggle, collapsed by default: page height
  2063 → 1554px with nothing removed. The baseline re-simulation moved onto the
  card, because the stale-probability fix had depended on that panel mounting —
  collapsing it would otherwise have silently restored the bug.
- **Grid rows no longer stretch panels.** CSS grid sizes every cell to the
  tallest in its row, so short panels rendered as mostly-empty boxes. Applied
  `items-start` only where dead space was *measured* in a browser (AI/Macro
  555px, Retirement 211, Funds 201, Risk 193, Holdings 124, Learn 112, Journal
  93). Overview was left alone — its chart pair is fixed-height and correctly
  equal, and served as the control. Sum across 15 tabs: **1176px → 154px**.

**Deliberately not done:** no third-party component library. The primitives are
hand-rolled against the flight-deck tokens and `shadcn` is already the base
(`components.json` + 13 components in `ui/`); adding HeroUI would mean two
design systems where the boundary is arbitrary. Recorded because it has now
come up twice.
