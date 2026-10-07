#include "monte_carlo.h"

#include <gtest/gtest.h>

#include <cmath>
#include <vector>

#include "risk_service.h"

namespace wr = wealthpilot::risk;

namespace {

wr::GoalSimInput MakeInput(double value, double mean, double vol, int months, double target,
                           std::uint64_t seed) {
  wr::GoalSimInput in;
  in.sleeves.push_back({value, mean, vol});
  in.monthly_contribution = 0.0;
  in.months_remaining = months;
  in.target_value = target;
  in.num_paths = 2000;
  in.seed = seed;
  return in;
}

}  // namespace

// --- Percentile --------------------------------------------------------------
TEST(PercentileTest, LinearInterpolation) {
  std::vector<double> sorted{10, 20, 30, 40, 50};
  EXPECT_DOUBLE_EQ(wr::Percentile(sorted, 0.0), 10.0);
  EXPECT_DOUBLE_EQ(wr::Percentile(sorted, 1.0), 50.0);
  EXPECT_DOUBLE_EQ(wr::Percentile(sorted, 0.5), 30.0);
  EXPECT_DOUBLE_EQ(wr::Percentile(sorted, 0.25), 20.0);
}

// --- Goal simulation: closed-form / determinism ------------------------------
TEST(GoalSimTest, ZeroVolatilityIsDeterministic) {
  // With zero volatility the ending value is value * exp(annual_mean).
  const double value = 100000.0;
  const double mean = 0.12;
  wr::GoalSimInput in = MakeInput(value, mean, /*vol=*/0.0, /*months=*/12,
                                  /*target=*/110000.0, /*seed=*/42);
  const wr::GoalSimResult r = wr::RunGoalSimulation(in);

  const double expected = value * std::exp(mean);
  EXPECT_NEAR(r.median_ending_value, expected, 1e-3);
  EXPECT_NEAR(r.p10_value, expected, 1e-3);
  EXPECT_NEAR(r.p90_value, expected, 1e-3);
  // Deterministic ending is above the 110k target -> probability 1.
  EXPECT_DOUBLE_EQ(r.probability_of_success, 1.0);
}

TEST(GoalSimTest, ZeroVolBelowTargetHasZeroProbability) {
  wr::GoalSimInput in = MakeInput(100000.0, 0.12, 0.0, 12, /*target=*/200000.0, 42);
  const wr::GoalSimResult r = wr::RunGoalSimulation(in);
  EXPECT_DOUBLE_EQ(r.probability_of_success, 0.0);
}

TEST(GoalSimTest, DeterministicGivenSeed) {
  wr::GoalSimInput in = MakeInput(100000.0, 0.10, 0.15, 60, 150000.0, /*seed=*/12345);
  const wr::GoalSimResult a = wr::RunGoalSimulation(in);
  const wr::GoalSimResult b = wr::RunGoalSimulation(in);
  EXPECT_DOUBLE_EQ(a.probability_of_success, b.probability_of_success);
  EXPECT_DOUBLE_EQ(a.median_ending_value, b.median_ending_value);
  EXPECT_DOUBLE_EQ(a.p10_value, b.p10_value);
  EXPECT_DOUBLE_EQ(a.p90_value, b.p90_value);
}

TEST(GoalSimTest, DifferentSeedsProduceDifferentPaths) {
  const wr::GoalSimResult a = wr::RunGoalSimulation(MakeInput(100000, 0.10, 0.15, 60, 150000, 1));
  const wr::GoalSimResult b = wr::RunGoalSimulation(MakeInput(100000, 0.10, 0.15, 60, 150000, 2));
  EXPECT_NE(a.median_ending_value, b.median_ending_value);
}

TEST(GoalSimTest, TargetAlreadyMetWithZeroMonths) {
  wr::GoalSimInput in = MakeInput(100000.0, 0.10, 0.20, /*months=*/0, /*target=*/50000.0, 7);
  const wr::GoalSimResult r = wr::RunGoalSimulation(in);
  EXPECT_DOUBLE_EQ(r.probability_of_success, 1.0);
  EXPECT_NEAR(r.median_ending_value, 100000.0, 1e-9);
}

TEST(GoalSimTest, MoreVolatilityWidensPercentileBand) {
  const wr::GoalSimResult low =
      wr::RunGoalSimulation(MakeInput(100000, 0.10, 0.05, 120, 200000, 99));
  const wr::GoalSimResult high =
      wr::RunGoalSimulation(MakeInput(100000, 0.10, 0.30, 120, 200000, 99));
  EXPECT_GT(high.p90_value - high.p10_value, low.p90_value - low.p10_value);
}

TEST(GoalSimTest, InitialShockLowersOutcome) {
  wr::GoalSimInput base = MakeInput(100000.0, 0.10, 0.18, 60, 200000.0, 42);
  const wr::GoalSimResult unshocked = wr::RunGoalSimulation(base);
  base.initial_shock = -0.30;  // 30% equity crash at t=0
  const wr::GoalSimResult shocked = wr::RunGoalSimulation(base);
  EXPECT_LT(shocked.median_ending_value, unshocked.median_ending_value);
  EXPECT_LE(shocked.probability_of_success, unshocked.probability_of_success);
}

TEST(GoalSimTest, ShockIsBetaScaledByVolatility) {
  // Near-cash sleeve (vol 0.02) barely moves; months=0 so ending == shocked value.
  wr::GoalSimInput cash = MakeInput(100000.0, 0.06, 0.02, /*months=*/0, /*target=*/1.0, 1);
  cash.initial_shock = -0.30;
  const double value = wr::RunGoalSimulation(cash).median_ending_value;
  EXPECT_NEAR(value, 100000.0 * (1.0 - 0.30 * (0.02 / 0.18)), 1.0);
}

// --- Portfolio risk ----------------------------------------------------------
TEST(PortfolioRiskTest, ConstantReturnsHaveNoRisk) {
  wr::PortfolioRiskInput in;
  in.confidence = 0.95;
  in.buckets.push_back({"growth", 100000.0, std::vector<double>(50, 0.0)});
  const wr::PortfolioRiskResult r = wr::RunPortfolioRisk(in);
  EXPECT_NEAR(r.var, 0.0, 1e-9);
  EXPECT_NEAR(r.cvar, 0.0, 1e-9);
}

TEST(PortfolioRiskTest, ContributionsSumToCVaR) {
  wr::PortfolioRiskInput in;
  in.confidence = 0.90;
  in.buckets.push_back({"growth", 60000.0, {0.02, -0.05, 0.01, -0.08, 0.03, -0.02, 0.04, -0.01}});
  in.buckets.push_back({"dividend", 40000.0, {0.01, -0.02, 0.00, -0.03, 0.01, -0.01, 0.02, 0.00}});
  const wr::PortfolioRiskResult r = wr::RunPortfolioRisk(in);

  EXPECT_GT(r.var, 0.0);
  EXPECT_GE(r.cvar, r.var * 0.0);  // sane
  double sum = 0.0;
  for (const auto& c : r.contributions) sum += c.contribution;
  EXPECT_NEAR(sum, r.cvar, 1e-6);
}

TEST(PortfolioRiskTest, EmptyInputReturnsZeros) {
  wr::PortfolioRiskInput in;
  const wr::PortfolioRiskResult r = wr::RunPortfolioRisk(in);
  EXPECT_DOUBLE_EQ(r.var, 0.0);
  EXPECT_DOUBLE_EQ(r.cvar, 0.0);
  EXPECT_DOUBLE_EQ(r.annual_volatility, 0.0);
  EXPECT_DOUBLE_EQ(r.max_drawdown, 0.0);
  EXPECT_TRUE(r.contributions.empty());
}

TEST(PortfolioRiskTest, AnnualVolatilityScalesWithFrequency) {
  // Alternating ±1% has a periodic SD of exactly 0.01.
  std::vector<double> returns;
  for (int i = 0; i < 60; ++i) returns.push_back(i % 2 == 0 ? 0.01 : -0.01);

  wr::PortfolioRiskInput in;
  in.buckets.push_back({"growth", 100000.0, returns});
  in.periods_per_year = 252.0;
  const wr::PortfolioRiskResult daily = wr::RunPortfolioRisk(in);
  EXPECT_NEAR(daily.annual_volatility, 0.01 * std::sqrt(252.0), 1e-9);

  in.periods_per_year = 12.0;
  const wr::PortfolioRiskResult monthly = wr::RunPortfolioRisk(in);
  EXPECT_NEAR(monthly.annual_volatility, 0.01 * std::sqrt(12.0), 1e-9);
}

TEST(PortfolioRiskTest, ConstantReturnsHaveZeroVolAndDrawdown) {
  wr::PortfolioRiskInput in;
  in.buckets.push_back({"growth", 100000.0, std::vector<double>(50, 0.005)});
  const wr::PortfolioRiskResult r = wr::RunPortfolioRisk(in);
  EXPECT_NEAR(r.annual_volatility, 0.0, 1e-12);
  EXPECT_NEAR(r.max_drawdown, 0.0, 1e-12);
}

TEST(PortfolioRiskTest, MaxDrawdownMatchesKnownSequence) {
  // Wealth path: 1.10 → 0.55 → 0.605; peak 1.10 → max drawdown = 1 - 0.55/1.10 = 0.5.
  wr::PortfolioRiskInput in;
  in.buckets.push_back({"growth", 100000.0, {0.10, -0.50, 0.10}});
  const wr::PortfolioRiskResult r = wr::RunPortfolioRisk(in);
  EXPECT_NEAR(r.max_drawdown, 0.5, 1e-12);
}

TEST(PortfolioRiskTest, DrawdownBeforeNewPeakIsCounted) {
  // Dip happens first, then the series recovers past the old peak — the dip
  // must still be reported.
  wr::PortfolioRiskInput in;
  in.buckets.push_back({"growth", 100000.0, {-0.20, 0.50, 0.10}});
  const wr::PortfolioRiskResult r = wr::RunPortfolioRisk(in);
  EXPECT_NEAR(r.max_drawdown, 0.20, 1e-12);
}

// --- Portfolio projection ----------------------------------------------------
TEST(ProjectionTest, ZeroVolatilityIsDeterministicPerMonth) {
  wr::PortfolioProjectionInput in;
  in.sleeves.push_back({100000.0, 0.12, 0.0});
  in.months = 12;
  in.num_paths = 500;
  in.seed = 3;

  const auto points = wr::RunPortfolioProjection(in);
  ASSERT_EQ(points.size(), 12u);
  for (const auto& p : points) {
    EXPECT_NEAR(p.p10, p.median, 1e-6);
    EXPECT_NEAR(p.p90, p.median, 1e-6);
  }
  EXPECT_NEAR(points.back().median, 100000.0 * std::exp(0.12), 1e-3);
  EXPECT_GT(points.back().median, points.front().median);
}

TEST(ProjectionTest, UncertaintyWidensWithHorizon) {
  wr::PortfolioProjectionInput in;
  in.sleeves.push_back({100000.0, 0.10, 0.25});
  in.months = 60;
  in.num_paths = 2000;
  in.seed = 7;

  const auto points = wr::RunPortfolioProjection(in);
  ASSERT_EQ(points.size(), 60u);
  const double early = points[5].p90 - points[5].p10;
  const double late = points[59].p90 - points[59].p10;
  EXPECT_GT(late, early);
}

TEST(ProjectionTest, ZeroMonthsIsEmpty) {
  wr::PortfolioProjectionInput in;
  in.sleeves.push_back({100000.0, 0.1, 0.1});
  in.months = 0;
  EXPECT_TRUE(wr::RunPortfolioProjection(in).empty());
}

// --- Retirement plan (accumulation + drawdown) -------------------------------
namespace {

// Zero-volatility plan so every assertion is a closed form, not a distribution.
wr::RetirementPlanInput MakeFlatPlan(double value, double mean, int accum_months,
                                     int draw_months) {
  wr::RetirementPlanInput in;
  in.sleeves.push_back({value, mean, 0.0});
  in.accumulation_months = accum_months;
  in.drawdown_months = draw_months;
  in.num_paths = 500;
  in.seed = 11;
  return in;
}

}  // namespace

TEST(RetirementPlanTest, ZeroVolAccumulationIsClosedForm) {
  wr::RetirementPlanInput in = MakeFlatPlan(100000.0, 0.12, /*accum=*/12, /*draw=*/0);
  in.target_value = 1.0;
  const wr::RetirementPlanResult r = wr::RunRetirementPlan(in);

  const double expected = 100000.0 * std::exp(0.12);
  EXPECT_NEAR(r.median_corpus, expected, 1e-3);
  EXPECT_NEAR(r.p10_corpus, expected, 1e-3);
  EXPECT_NEAR(r.p90_corpus, expected, 1e-3);
  EXPECT_DOUBLE_EQ(r.probability_of_success, 1.0);
  EXPECT_DOUBLE_EQ(r.depletion_probability, 0.0);
  EXPECT_DOUBLE_EQ(r.median_depletion_month, -1.0);
}

TEST(RetirementPlanTest, ContributionScheduleStepsUp) {
  // 24 months: 1,000/mo for the first year, 10,000/mo for the second. With no
  // growth the corpus is exactly the sum of contributions.
  wr::RetirementPlanInput in = MakeFlatPlan(0.0, 0.0, /*accum=*/24, /*draw=*/0);
  in.contribution_schedule.assign(12, 1000.0);
  in.contribution_schedule.resize(24, 10000.0);
  in.target_value = 1.0;

  const wr::RetirementPlanResult r = wr::RunRetirementPlan(in);
  EXPECT_NEAR(r.median_corpus, 12 * 1000.0 + 12 * 10000.0, 1e-6);
}

TEST(RetirementPlanTest, ShortScheduleHoldsItsLastValue) {
  // Only the first 12 months are specified; months 12-23 should hold 10,000.
  wr::RetirementPlanInput in = MakeFlatPlan(0.0, 0.0, /*accum=*/24, /*draw=*/0);
  in.contribution_schedule.assign(11, 1000.0);
  in.contribution_schedule.push_back(10000.0);
  in.target_value = 1.0;

  const wr::RetirementPlanResult r = wr::RunRetirementPlan(in);
  EXPECT_NEAR(r.median_corpus, 11 * 1000.0 + 13 * 10000.0, 1e-6);
}

TEST(RetirementPlanTest, EmptyScheduleFallsBackToScalar) {
  wr::RetirementPlanInput in = MakeFlatPlan(0.0, 0.0, /*accum=*/10, /*draw=*/0);
  in.monthly_contribution = 500.0;
  in.target_value = 1.0;

  const wr::RetirementPlanResult r = wr::RunRetirementPlan(in);
  EXPECT_NEAR(r.median_corpus, 10 * 500.0, 1e-6);
}

TEST(RetirementPlanTest, DrawdownDepletesOnSchedule) {
  // No growth, 1,200 corpus, 100/mo withdrawn -> dry after exactly 12 months.
  wr::RetirementPlanInput in = MakeFlatPlan(1200.0, 0.0, /*accum=*/0, /*draw=*/24);
  in.withdrawal_schedule.assign(24, 100.0);
  in.target_value = 1.0;

  const wr::RetirementPlanResult r = wr::RunRetirementPlan(in);
  EXPECT_DOUBLE_EQ(r.depletion_probability, 1.0);
  EXPECT_NEAR(r.median_depletion_month, 12.0, 1e-6);
  EXPECT_NEAR(r.median_terminal_value, 0.0, 1e-6);
  // Retiring today: the boundary corpus is what's on the table now, not what's
  // left after the drawdown.
  EXPECT_NEAR(r.median_corpus, 1200.0, 1e-6);
}

TEST(RetirementPlanTest, WithdrawalBelowGrowthSurvives) {
  // 10% nominal growth on 1,000,000 is ~8,300/mo; drawing 2,000 never runs dry.
  wr::RetirementPlanInput in = MakeFlatPlan(1000000.0, 0.10, /*accum=*/0, /*draw=*/240);
  in.withdrawal_schedule.assign(240, 2000.0);
  in.target_value = 1.0;

  const wr::RetirementPlanResult r = wr::RunRetirementPlan(in);
  EXPECT_DOUBLE_EQ(r.depletion_probability, 0.0);
  EXPECT_GT(r.median_terminal_value, 1000000.0);
}

TEST(RetirementPlanTest, BandsAreYearlyAndSpanBothPhases) {
  wr::RetirementPlanInput in = MakeFlatPlan(100000.0, 0.08, /*accum=*/24, /*draw=*/36);
  in.target_value = 1.0;

  const wr::RetirementPlanResult r = wr::RunRetirementPlan(in);
  ASSERT_FALSE(r.bands.empty());
  EXPECT_EQ(r.bands.front().month, 0);
  EXPECT_NEAR(r.bands.front().median, 100000.0, 1e-6);  // month 0 == today
  EXPECT_EQ(r.bands.back().month, 60);                  // 24 accum + 36 drawdown
  for (std::size_t i = 1; i < r.bands.size(); ++i) {
    EXPECT_GT(r.bands[i].month, r.bands[i - 1].month);
  }
}

TEST(RetirementPlanTest, SequenceRiskHurtsWhenDrawingDown) {
  // Same expected return, but volatility plus withdrawals destroys capital in a
  // way a deterministic projection hides — the whole reason both phases run on
  // one path. The volatile plan should run dry on a meaningful share of paths.
  wr::RetirementPlanInput calm = MakeFlatPlan(5000000.0, 0.10, /*accum=*/0, /*draw=*/360);
  calm.withdrawal_schedule.assign(360, 40000.0);
  calm.num_paths = 2000;

  wr::RetirementPlanInput rough = calm;
  rough.sleeves[0].annual_return_volatility = 0.30;

  EXPECT_DOUBLE_EQ(wr::RunRetirementPlan(calm).depletion_probability, 0.0);
  EXPECT_GT(wr::RunRetirementPlan(rough).depletion_probability, 0.05);
}

TEST(RetirementPlanTest, DeterministicGivenSeed) {
  wr::RetirementPlanInput in = MakeFlatPlan(500000.0, 0.10, /*accum=*/60, /*draw=*/60);
  in.sleeves[0].annual_return_volatility = 0.18;
  in.monthly_contribution = 5000.0;
  in.withdrawal_schedule.assign(60, 20000.0);
  in.target_value = 1000000.0;
  in.num_paths = 2000;

  const wr::RetirementPlanResult a = wr::RunRetirementPlan(in);
  const wr::RetirementPlanResult b = wr::RunRetirementPlan(in);
  EXPECT_DOUBLE_EQ(a.probability_of_success, b.probability_of_success);
  EXPECT_DOUBLE_EQ(a.median_corpus, b.median_corpus);
  EXPECT_DOUBLE_EQ(a.depletion_probability, b.depletion_probability);
}

TEST(RetirementPlanTest, EmptyInputIsSafe) {
  wr::RetirementPlanInput in;
  const wr::RetirementPlanResult r = wr::RunRetirementPlan(in);
  EXPECT_TRUE(r.bands.empty());
  EXPECT_DOUBLE_EQ(r.probability_of_success, 0.0);
}

// --- Diversification ---------------------------------------------------------
TEST(DiversificationTest, PerfectlyCorrelatedNoBenefit) {
  wr::DivAsset a{"A", 1.0, {0.01, -0.02, 0.03, -0.01, 0.02}};
  wr::DivAsset b{"B", 1.0, {0.02, -0.04, 0.06, -0.02, 0.04}};  // 2x A

  const auto r = wr::RunDiversification({a, b});
  EXPECT_EQ(r.holdings, 2);
  EXPECT_NEAR(r.average_correlation, 1.0, 1e-6);
  EXPECT_NEAR(r.diversification_ratio, 1.0, 1e-6);
  ASSERT_EQ(r.top_pairs.size(), 1u);
  EXPECT_NEAR(r.top_pairs[0].correlation, 1.0, 1e-6);
}

TEST(DiversificationTest, NegativelyCorrelatedGivesBenefit) {
  wr::DivAsset a{"A", 1.0, {0.03, -0.02, 0.04, -0.01, 0.02}};
  wr::DivAsset b{"B", 1.0, {-0.02, 0.03, -0.01, 0.02, -0.03}};

  const auto r = wr::RunDiversification({a, b});
  EXPECT_LT(r.average_correlation, 0.0);
  EXPECT_GT(r.diversification_ratio, 1.0);  // combining cuts portfolio vol
}

TEST(DiversificationTest, EffectiveHoldingsReflectsConcentration) {
  wr::DivAsset big{"BIG", 0.9, {0.01, 0.02, -0.01}};
  wr::DivAsset small{"SMALL", 0.1, {0.02, -0.01, 0.0}};

  const auto r = wr::RunDiversification({big, small});
  EXPECT_NEAR(r.effective_holdings, 1.0 / (0.81 + 0.01), 1e-6);
  EXPECT_LT(r.effective_holdings, 2.0);  // concentrated
}

// --- Service marshalling -----------------------------------------------------
TEST(RiskServiceTest, HealthReturnsOk) {
  wr::RiskEngineServiceImpl service;
  wr::HealthRequest request;
  wr::HealthResponse response;
  const grpc::Status status = service.Health(nullptr, &request, &response);
  EXPECT_TRUE(status.ok());
  EXPECT_EQ(response.status(), "ok");
}

TEST(RiskServiceTest, SimulateGoalProbabilityMarshalsResult) {
  wr::RiskEngineServiceImpl service;
  wr::GoalSimRequest request;
  auto* sleeve = request.add_sleeves();
  sleeve->set_bucket("debt");
  sleeve->set_value(100000.0);
  sleeve->set_annual_return_mean(0.07);
  sleeve->set_annual_return_volatility(0.0);
  request.set_months_remaining(12);
  request.set_target_value(100000.0);
  request.set_num_paths(500);
  request.set_seed(11);

  wr::GoalSimResponse response;
  const grpc::Status status = service.SimulateGoalProbability(nullptr, &request, &response);
  EXPECT_TRUE(status.ok());
  EXPECT_DOUBLE_EQ(response.probability_of_success(), 1.0);  // 7% growth clears target
  EXPECT_GT(response.median_ending_value(), 100000.0);
}
