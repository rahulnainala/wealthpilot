# Phase 52 — Account Aggregator (design spike, NOT yet implemented)

**Status: SPIKE / BLOCKED on an external provider account.** This phase is
deliberately *not* coded end-to-end. India's Account Aggregator (AA) framework
requires a registered **TSP/FIU relationship** (Setu, Finvu, Onemoney, …) with a
signed agreement, a registered `FIU-ID`, and webhook callbacks reachable over
HTTPS. None of that can be stood up from a local dev box, and shipping a stub
that *looks* live would be dishonest about where real money data comes from.
This document scopes the work so it can be picked up once a provider is onboarded.

## What AA would add

Today net worth (Phase 49) blends the Kite portfolio with **manually entered**
external assets. AA replaces the manual entry with a consented, read-only pull of
bank balances, deposits, mutual funds (non-Zerodha), and insurance — refreshed on
a schedule — so the net-worth and FI numbers stop drifting from reality.

## Architecture (proposed)

```
User ── consent ──▶ AA app (Finvu/Onemoney)         WealthPilot (FIU)
   ▲                     │  approves accounts            │
   │                     ▼                               ▼
   └──── redirect ── TSP (Setu) ──── FI data ──▶  /api/aa/webhook ──▶ aa_service
                                                         │
                                                   external_asset rows
                                                   (source = "aa:<fip>")
```

- **`backend/app/services/aa/client.py`** — thin TSP REST wrapper: create consent,
  poll consent status, request an FI session, fetch + decrypt the FI data payload
  (ECDH key material per the ReBIT FI data spec).
- **`backend/app/routers/aa.py`** (behind `RequireAuth`):
  - `POST /api/aa/consent` → returns the AA redirect URL for the owner to approve.
  - `GET  /api/aa/consent/{handle}` → consent status.
  - `POST /api/aa/webhook` → TSP notification sink (consent + FI-data ready).
  - `POST /api/aa/refresh` → trigger an FI-data fetch for active consents.
- **Storage** — reuse the `external_asset` table from Phase 49 with a `source`
  column (`"manual"` vs `"aa:<fip-id>"`) and a `last_synced_at`; AA-sourced rows
  are read-only in the UI. A separate `aa_consent` table tracks consent handles,
  status, and expiry.
- **Folds into** the existing net-worth aggregation and FI projection unchanged —
  AA just becomes another asset source.

## Hard prerequisites (the actual blockers)

1. A **TSP account** (Setu recommended for sandbox ergonomics) and an FIU
   registration — commercial onboarding, not self-serve.
2. A **public HTTPS callback** for webhooks — the Phase 41 Caddy deploy on
   `finance.rahulnainala.com` already provides this once live.
3. **Consent artefact + encryption**: implement the ReBIT consent schema and the
   ECDH/AES FI-data decryption exactly, or data fetches fail signature checks.
4. **Secrets**: `AA_TSP_BASE_URL`, `AA_FIU_ID`, `AA_API_KEY`, `AA_PRIVATE_KEY`
   in the env layering (never committed).

## Recommended sequencing when unblocked

1. Sandbox spike against Setu's mock FIP — consent → session → decrypt one bank
   account, printed to logs. Timebox to prove the crypto handshake.
2. Persist to `external_asset` with `source="aa:*"`, wire the refresh job.
3. UI: an "Link via Account Aggregator" button on the Net-worth panel; AA rows
   render read-only with a synced-at badge.
4. Schedule a periodic refresh (respect consent frequency limits).

Until step 0 (a provider account) exists, this stays a documented spike.
