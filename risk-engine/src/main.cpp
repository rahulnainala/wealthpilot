#include <grpcpp/grpcpp.h>

#include <cstdlib>
#include <iostream>
#include <string>

#include "risk_service.h"

int main() {
  const char* port_env = std::getenv("RISK_ENGINE_PORT");
  const std::string port = port_env != nullptr ? port_env : "50051";
  const std::string server_address = "0.0.0.0:" + port;

  wealthpilot::risk::RiskEngineServiceImpl service;

  grpc::ServerBuilder builder;
  builder.AddListeningPort(server_address, grpc::InsecureServerCredentials());
  builder.RegisterService(&service);

  std::unique_ptr<grpc::Server> server(builder.BuildAndStart());
  std::cout << "risk-engine gRPC server listening on " << server_address << std::endl;
  server->Wait();

  return 0;
}
