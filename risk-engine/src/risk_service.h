#pragma once

#include <grpcpp/grpcpp.h>

#include "risk.grpc.pb.h"

namespace wealthpilot::risk {

// Single service implementation for all RiskEngine RPCs. The simulation logic
// lives in monte_carlo.* (pure, testable); this class only marshals proto
// messages to/from those functions.
class RiskEngineServiceImpl final : public RiskEngine::Service {
 public:
  grpc::Status Health(grpc::ServerContext* context, const HealthRequest* request,
                      HealthResponse* response) override;

  grpc::Status SimulateGoalProbability(grpc::ServerContext* context, const GoalSimRequest* request,
                                       GoalSimResponse* response) override;

  grpc::Status ComputePortfolioRisk(grpc::ServerContext* context,
                                    const PortfolioRiskRequest* request,
                                    PortfolioRiskResponse* response) override;

  grpc::Status SimulatePortfolioProjection(grpc::ServerContext* context,
                                           const PortfolioProjectionRequest* request,
                                           PortfolioProjectionResponse* response) override;

  grpc::Status ComputeDiversification(grpc::ServerContext* context,
                                      const DiversificationRequest* request,
                                      DiversificationResponse* response) override;

  grpc::Status SimulateRetirementPlan(grpc::ServerContext* context,
                                      const RetirementPlanRequest* request,
                                      RetirementPlanResponse* response) override;
};

}  // namespace wealthpilot::risk
