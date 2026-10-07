#include "risk_service.h"

#include <chrono>
#include <iostream>
#include <sstream>

#include "monte_carlo.h"

namespace wealthpilot::risk {

namespace {

// Logs one line per completed RPC so `docker logs` shows real traffic.
class RpcLog {
 public:
  explicit RpcLog(const char* method) : method_(method), start_(std::chrono::steady_clock::now()) {}

  RpcLog(const RpcLog&) = delete;
  RpcLog& operator=(const RpcLog&) = delete;

  ~RpcLog() {
    const auto elapsed = std::chrono::steady_clock::now() - start_;
    const double ms =
        std::chrono::duration_cast<std::chrono::duration<double, std::milli>>(elapsed).count();
    std::cout << "[rpc] " << method_ << detail_.str() << " (" << ms << " ms)" << std::endl;
  }

  std::ostringstream& detail() { return detail_; }

 private:
  const char* method_;
  std::chrono::steady_clock::time_point start_;
  std::ostringstream detail_;
};

}  // namespace

grpc::Status RiskEngineServiceImpl::Health(grpc::ServerContext* /*context*/,
                                           const HealthRequest* /*request*/,
                                           HealthResponse* response) {
  response->set_status("ok");
  return grpc::Status::OK;
}

grpc::Status RiskEngineServiceImpl::SimulateGoalProbability(grpc::ServerContext* /*context*/,
                                                            const GoalSimRequest* request,
                                                            GoalSimResponse* response) {
  RpcLog log("SimulateGoalProbability");
  log.detail() << " sleeves=" << request->sleeves_size()
               << " months=" << request->months_remaining() << " paths=" << request->num_paths();

  GoalSimInput input;
  input.sleeves.reserve(static_cast<std::size_t>(request->sleeves_size()));
  for (const auto& sleeve : request->sleeves()) {
    input.sleeves.push_back(
        {sleeve.value(), sleeve.annual_return_mean(), sleeve.annual_return_volatility()});
  }
  input.monthly_contribution = request->monthly_contribution();
  input.months_remaining = request->months_remaining();
  input.target_value = request->target_value();
  input.num_paths = request->num_paths();
  input.seed = request->seed();
  input.initial_shock = request->initial_shock();

  const GoalSimResult result = RunGoalSimulation(input);
  response->set_probability_of_success(result.probability_of_success);
  response->set_median_ending_value(result.median_ending_value);
  response->set_p10_value(result.p10_value);
  response->set_p90_value(result.p90_value);
  return grpc::Status::OK;
}

grpc::Status RiskEngineServiceImpl::ComputePortfolioRisk(grpc::ServerContext* /*context*/,
                                                         const PortfolioRiskRequest* request,
                                                         PortfolioRiskResponse* response) {
  RpcLog log("ComputePortfolioRisk");
  log.detail() << " buckets=" << request->buckets_size();

  PortfolioRiskInput input;
  input.confidence = request->confidence();
  if (request->periods_per_year() > 0.0) input.periods_per_year = request->periods_per_year();
  input.buckets.reserve(static_cast<std::size_t>(request->buckets_size()));
  for (const auto& bucket : request->buckets()) {
    BucketSeries series;
    series.bucket = bucket.bucket();
    series.value = bucket.value();
    series.returns.assign(bucket.returns().begin(), bucket.returns().end());
    input.buckets.push_back(std::move(series));
  }

  const PortfolioRiskResult result = RunPortfolioRisk(input);
  response->set_var(result.var);
  response->set_cvar(result.cvar);
  response->set_annual_volatility(result.annual_volatility);
  response->set_max_drawdown(result.max_drawdown);
  for (const auto& contribution : result.contributions) {
    RiskContribution* out = response->add_contributions();
    out->set_bucket(contribution.bucket);
    out->set_contribution(contribution.contribution);
  }
  return grpc::Status::OK;
}

grpc::Status RiskEngineServiceImpl::SimulatePortfolioProjection(
    grpc::ServerContext* /*context*/, const PortfolioProjectionRequest* request,
    PortfolioProjectionResponse* response) {
  RpcLog log("SimulatePortfolioProjection");
  log.detail() << " sleeves=" << request->sleeves_size() << " months=" << request->months()
               << " paths=" << request->num_paths();

  PortfolioProjectionInput input;
  input.sleeves.reserve(static_cast<std::size_t>(request->sleeves_size()));
  for (const auto& sleeve : request->sleeves()) {
    input.sleeves.push_back(
        {sleeve.value(), sleeve.annual_return_mean(), sleeve.annual_return_volatility()});
  }
  input.monthly_contribution = request->monthly_contribution();
  input.months = request->months();
  input.num_paths = request->num_paths();
  input.seed = request->seed();

  for (const ProjectionBand& band : RunPortfolioProjection(input)) {
    auto* out = response->add_points();
    out->set_month(band.month);
    out->set_p10(band.p10);
    out->set_median(band.median);
    out->set_p90(band.p90);
  }
  return grpc::Status::OK;
}

grpc::Status RiskEngineServiceImpl::ComputeDiversification(grpc::ServerContext* /*context*/,
                                                           const DiversificationRequest* request,
                                                           DiversificationResponse* response) {
  RpcLog log("ComputeDiversification");
  log.detail() << " assets=" << request->assets_size();

  std::vector<DivAsset> assets;
  assets.reserve(static_cast<std::size_t>(request->assets_size()));
  for (const auto& a : request->assets()) {
    DivAsset asset;
    asset.label = a.label();
    asset.weight = a.weight();
    asset.returns.assign(a.returns().begin(), a.returns().end());
    assets.push_back(std::move(asset));
  }

  const DiversificationResult result = RunDiversification(assets);
  response->set_average_correlation(result.average_correlation);
  response->set_diversification_ratio(result.diversification_ratio);
  response->set_effective_holdings(result.effective_holdings);
  response->set_holdings(result.holdings);
  for (const CorrPair& pair : result.top_pairs) {
    auto* out = response->add_top_pairs();
    out->set_label_a(pair.a);
    out->set_label_b(pair.b);
    out->set_correlation(pair.correlation);
  }
  return grpc::Status::OK;
}

grpc::Status RiskEngineServiceImpl::SimulateRetirementPlan(grpc::ServerContext* /*context*/,
                                                           const RetirementPlanRequest* request,
                                                           RetirementPlanResponse* response) {
  RpcLog log("SimulateRetirementPlan");
  log.detail() << " sleeves=" << request->sleeves_size()
               << " accum=" << request->accumulation_months()
               << " draw=" << request->drawdown_months() << " paths=" << request->num_paths();

  RetirementPlanInput input;
  input.sleeves.reserve(static_cast<std::size_t>(request->sleeves_size()));
  for (const auto& sleeve : request->sleeves()) {
    input.sleeves.push_back(
        {sleeve.value(), sleeve.annual_return_mean(), sleeve.annual_return_volatility()});
  }
  input.contribution_schedule.assign(request->contribution_schedule().begin(),
                                     request->contribution_schedule().end());
  input.monthly_contribution = request->monthly_contribution();
  input.accumulation_months = request->accumulation_months();
  input.target_value = request->target_value();
  input.withdrawal_schedule.assign(request->withdrawal_schedule().begin(),
                                   request->withdrawal_schedule().end());
  input.drawdown_months = request->drawdown_months();
  input.num_paths = request->num_paths();
  input.seed = request->seed();

  const RetirementPlanResult result = RunRetirementPlan(input);
  response->set_probability_of_success(result.probability_of_success);
  response->set_median_corpus(result.median_corpus);
  response->set_p10_corpus(result.p10_corpus);
  response->set_p90_corpus(result.p90_corpus);
  response->set_depletion_probability(result.depletion_probability);
  response->set_median_depletion_month(result.median_depletion_month);
  response->set_median_terminal_value(result.median_terminal_value);
  for (const ProjectionBand& band : result.bands) {
    auto* out = response->add_bands();
    out->set_month(band.month);
    out->set_p10(band.p10);
    out->set_median(band.median);
    out->set_p90(band.p90);
  }
  return grpc::Status::OK;
}

}  // namespace wealthpilot::risk
