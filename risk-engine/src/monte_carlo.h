#pragma once

#include <cstdint>
#include <string>
#include <vector>

namespace wealthpilot::risk {

// --- Goal probability simulation ---------------------------------------------

// One allocation sleeve: money in a bucket with its own return assumptions.
struct Sleeve {
  double value = 0.0;
  double annual_return_mean = 0.0;        // decimal (0.11 == 11%)
  double annual_return_volatility = 0.0;  // decimal (0.16 == 16%)
};

struct GoalSimInput {
  std::vector<Sleeve> sleeves;
  double monthly_contribution = 0.0;
  int months_remaining = 0;
  double target_value = 0.0;
  int num_paths = 0;           // <= 0 -> kDefaultPaths
  std::uint64_t seed = 0;      // 0 -> nondeterministic
  double initial_shock = 0.0;  // <= 0: one-time shock at t=0, beta-scaled by vol
};

struct GoalSimResult {
  double probability_of_success = 0.0;
  double median_ending_value = 0.0;
  double p10_value = 0.0;
  double p90_value = 0.0;
};

inline constexpr int kDefaultPaths = 10000;

// Multi-threaded Monte Carlo. Deterministic when `seed` != 0 (independent of the
// number of worker threads, because each path is seeded from (seed, path_index)).
GoalSimResult RunGoalSimulation(const GoalSimInput& input);

// --- Portfolio risk (historical VaR / CVaR) ----------------------------------

struct BucketSeries {
  std::string bucket;
  double value = 0.0;
  std::vector<double> returns;  // historical periodic returns
};

// Named to avoid colliding with the generated proto message RiskContribution.
struct BucketContribution {
  std::string bucket;
  double contribution = 0.0;  // component contribution to CVaR (rupees)
};

struct PortfolioRiskInput {
  std::vector<BucketSeries> buckets;
  double confidence = 0.95;
  double periods_per_year = 252.0;  // frequency of the return series (daily default)
};

struct PortfolioRiskResult {
  double var = 0.0;                // rupees, positive = loss
  double cvar = 0.0;               // rupees, positive = loss
  double annual_volatility = 0.0;  // annualized portfolio vol (decimal)
  double max_drawdown = 0.0;       // worst peak-to-trough over the window (decimal)
  std::vector<BucketContribution> contributions;
};

PortfolioRiskResult RunPortfolioRisk(const PortfolioRiskInput& input);

// --- Portfolio projection (forward Monte Carlo fan chart) ---------------------

struct PortfolioProjectionInput {
  std::vector<Sleeve> sleeves;
  double monthly_contribution = 0.0;
  int months = 0;
  int num_paths = 0;       // <= 0 -> kDefaultPaths
  std::uint64_t seed = 0;  // 0 -> nondeterministic
};

// Named to avoid colliding with the generated proto message ProjectionPoint.
struct ProjectionBand {
  int month = 0;
  double p10 = 0.0;
  double median = 0.0;
  double p90 = 0.0;
};

// Simulate the total portfolio value forward, returning p10/median/p90 per month.
std::vector<ProjectionBand> RunPortfolioProjection(const PortfolioProjectionInput& input);

// --- Retirement plan (accumulation + drawdown on one path) --------------------

struct RetirementPlanInput {
  std::vector<Sleeve> sleeves;
  // Per-month contribution during accumulation. Empty -> `monthly_contribution`
  // for every month; shorter than the phase -> the last value extends. This is
  // what lets a plan step up as other goals complete and free their SIPs.
  std::vector<double> contribution_schedule;
  double monthly_contribution = 0.0;  // fallback when the schedule is empty
  int accumulation_months = 0;
  double target_value = 0.0;  // nominal corpus wanted at retirement
  // Per-month withdrawal during drawdown, nominal (so the caller bakes in
  // inflation). Same empty/short semantics as the contribution schedule.
  std::vector<double> withdrawal_schedule;
  int drawdown_months = 0;
  int num_paths = 0;       // <= 0 -> kDefaultPaths
  std::uint64_t seed = 0;  // 0 -> nondeterministic
};

struct RetirementPlanResult {
  // At the retirement boundary.
  double probability_of_success = 0.0;  // fraction of paths with corpus >= target
  double median_corpus = 0.0;
  double p10_corpus = 0.0;
  double p90_corpus = 0.0;
  // Through the drawdown phase.
  double depletion_probability = 0.0;    // fraction that ran dry before the end
  double median_depletion_month = -1.0;  // among depleting paths; -1 if none
  double median_terminal_value = 0.0;    // corpus left at the end of drawdown
  // p10/median/p90 sampled yearly across BOTH phases (month 0 included).
  std::vector<ProjectionBand> bands;
};

// One continuous Monte Carlo per path: contribute through accumulation, then
// withdraw through retirement. Running both phases on the same path is the
// point — it carries sequence-of-returns risk across the boundary, which is
// exactly where it does the most damage and what simulating the two phases
// separately would hide.
RetirementPlanResult RunRetirementPlan(const RetirementPlanInput& input);

// --- Diversification & concentration -----------------------------------------

// Named to avoid colliding with the generated proto messages of the same intent.
struct DivAsset {
  std::string label;
  double weight = 0.0;  // value share (need not be normalised)
  std::vector<double> returns;
};

struct CorrPair {
  std::string a;
  std::string b;
  double correlation = 0.0;
};

struct DiversificationResult {
  double average_correlation = 0.0;
  double diversification_ratio = 1.0;
  double effective_holdings = 0.0;
  int holdings = 0;
  std::vector<CorrPair> top_pairs;
};

// Correlation-based diversification: weighted average pairwise correlation, the
// diversification ratio (weighted-avg vol / portfolio vol), effective number of
// holdings (1 / HHI of weights), and the most-correlated pairs.
DiversificationResult RunDiversification(const std::vector<DivAsset>& assets);

// Exposed for testing: linear-interpolated percentile of a sorted vector.
double Percentile(const std::vector<double>& sorted, double q);

}  // namespace wealthpilot::risk
