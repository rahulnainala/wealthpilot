cmake_minimum_required(VERSION 3.20)
project(wealthpilot_risk_engine CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()

find_package(Threads REQUIRED)
# gRPC::grpc++ pulls in protobuf transitively (in whichever mode its own package needs).
# We deliberately don't find_package(Protobuf) ourselves: Homebrew's protobuf ships a CONFIG
# package that gRPC's CONFIG package also depends on, and calling find_package(Protobuf) in
# Module mode first (needed for Debian/apt, which has no protobuf CMake config at all) redefines
# the same imported targets and conflicts with gRPC's own config-mode dependency resolution.
find_package(gRPC CONFIG REQUIRED)

# protoc/grpc_cpp_plugin are located as plain executables (present on PATH on both Homebrew and
# Debian/apt) rather than via CMake targets, since only one of the two platforms exposes a
# protobuf::protoc imported target.
find_program(PROTOC_EXECUTABLE protoc REQUIRED)
find_program(GRPC_CPP_PLUGIN grpc_cpp_plugin REQUIRED)

set(PROTO_FILE ${CMAKE_CURRENT_SOURCE_DIR}/proto/risk.proto)
set(GENERATED_DIR ${CMAKE_CURRENT_BINARY_DIR}/generated)
file(MAKE_DIRECTORY ${GENERATED_DIR})

set(PROTO_SRCS ${GENERATED_DIR}/risk.pb.cc)
set(PROTO_HDRS ${GENERATED_DIR}/risk.pb.h)
set(GRPC_SRCS ${GENERATED_DIR}/risk.grpc.pb.cc)
set(GRPC_HDRS ${GENERATED_DIR}/risk.grpc.pb.h)

add_custom_command(
  OUTPUT ${PROTO_SRCS} ${PROTO_HDRS} ${GRPC_SRCS} ${GRPC_HDRS}
  COMMAND ${PROTOC_EXECUTABLE}
  ARGS --grpc_out=${GENERATED_DIR}
       --cpp_out=${GENERATED_DIR}
       --plugin=protoc-gen-grpc=${GRPC_CPP_PLUGIN}
       -I ${CMAKE_CURRENT_SOURCE_DIR}/proto
       ${PROTO_FILE}
  DEPENDS ${PROTO_FILE}
)

add_library(risk_proto STATIC ${PROTO_SRCS} ${GRPC_SRCS})
target_link_libraries(risk_proto PUBLIC gRPC::grpc++)
target_include_directories(risk_proto PUBLIC ${GENERATED_DIR})

add_library(risk_engine_lib STATIC
  src/monte_carlo.cpp
  src/risk_service.cpp
)
target_include_directories(risk_engine_lib PUBLIC src)
target_link_libraries(risk_engine_lib PUBLIC risk_proto)

add_executable(risk_engine_server src/main.cpp)
target_link_libraries(risk_engine_server PRIVATE risk_engine_lib Threads::Threads)

enable_testing()
add_subdirectory(tests)
