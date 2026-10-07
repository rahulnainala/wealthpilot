import type { Page } from "@playwright/test";

const SNAPSHOT = {
  id: 1,
  ts: "2026-07-07T04:15:00+00:00",
  status: "ok",
  total_value: 74210.4,
  invested: 70865.3,
  cash: 2450.0,
  error: null,
  bucket_values: { dividend: 28140.5, other: 3708.0, mf: 42361.9 },
  holdings: [
    {
      symbol: "IOC",
      name: null,
      type: "stock",
      bucket: "dividend",
      qty: 30,
      avg_price: 151.2,
      last_price: 146.1,
      value: 4383.0,
      invested: 4536.0,
      pnl: -153.0,
    },
    {
      symbol: "INF789F01XA0",
      name: "UTI Nifty 50 Index Fund - Direct Growth",
      type: "mf",
      bucket: "mf",
      qty: 62.5,
      avg_price: 158.4,
      last_price: 168.59,
      value: 10536.88,
      invested: 9900.0,
      pnl: 636.88,
    },
  ],
};

const MARKET = {
  is_fixture: true,
  indices: [
    { name: "NIFTY 50", instrument_token: 256265, last_price: 24850, change_pct: 0.4 },
    { name: "NIFTY BANK", instrument_token: 260105, last_price: 53200, change_pct: 0.2 },
  ],
};

const GOALS_ANALYSIS = [
  {
    key: "travel",
    name: "Travel Fund",
    months_remaining: 43,
    pct_elapsed: 0,
    assigned_value: 4226.4,
    assigned_symbols: ["INF179K01YM7"],
    violations: [],
    simulation: {
      probability_of_success: 0.29,
      median_ending_value: 509325,
      p10_value: 430100,
      p90_value: 641800,
      run_ts: "2026-07-07T04:15:00+00:00",
    },
  },
];

const GOALS = [
  {
    id: 1,
    key: "travel",
    name: "Travel Fund",
    start_date: "2026-08-01",
    target_date: "2030-02-01",
    checkpoint_date: null,
    target_value: 600000,
    monthly_contribution: 10000,
    assigned_isins: ["INF179K01YM7"],
    assigned_buckets: [],
    notes: null,
  },
];

/** Intercept backend API calls and reply with deterministic fixture data. */
export async function mockApi(page: Page): Promise<void> {
  const json = (data: unknown) => ({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify(data),
  });

  // Auth off, as in local/mock mode — otherwise the app stops at the password gate.
  await page.route("**/api/auth/config", (r) => r.fulfill(json({ auth_enabled: false })));
  await page.route("**/api/snapshots/latest", (r) => r.fulfill(json(SNAPSHOT)));
  await page.route("**/api/snapshots/refresh", (r) => r.fulfill(json(SNAPSHOT)));
  await page.route("**/api/market/overview", (r) => r.fulfill(json(MARKET)));
  await page.route("**/api/analytics/goals", (r) => r.fulfill(json(GOALS_ANALYSIS)));
  await page.route("**/api/goals", (r) => r.fulfill(json(GOALS)));
}
