import { expect, test } from "@playwright/test";

import { mockApi } from "./fixtures";

test("dashboard renders overview, market and goal-simulation with mock data", async ({
  page,
}) => {
  await mockApi(page);
  await page.goto("/");

  // Header + Overview KPIs.
  await expect(page.getByRole("heading", { name: "WealthPilot" })).toBeVisible();
  await expect(page.getByText("Total portfolio value")).toBeVisible();
  await expect(page.getByText("Unrealized P&L")).toBeVisible();

  // A holding from the fixture snapshot.
  await page.getByRole("tab", { name: "Portfolio" }).click();
  await expect(page.getByText("IOC", { exact: true }).first()).toBeVisible();

  // Market tab shows the curated indices.
  await page.getByRole("tab", { name: "Market" }).click();
  await expect(page.getByText("NIFTY 50", { exact: true }).first()).toBeVisible();
  await expect(page.getByText(/fixture data/i)).toBeVisible();

  // Goals tab shows the Monte Carlo simulation panel.
  await page.getByRole("tab", { name: "Goals" }).click();
  await expect(page.getByRole("heading", { name: /Travel Fund/ }).first()).toBeVisible();
  await expect(page.getByText("Probability of hitting target").filter({ visible: true }).first()).toBeVisible();
  await expect(page.getByText("29%", { exact: true }).filter({ visible: true }).first()).toBeVisible();
});
