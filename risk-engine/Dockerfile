FROM debian:bookworm-slim AS builder
WORKDIR /src

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    pkg-config \
    protobuf-compiler \
    protobuf-compiler-grpc \
    libprotobuf-dev \
    libgrpc++-dev \
    libgtest-dev \
    && rm -rf /var/lib/apt/lists/*

COPY . .
RUN cmake -S . -B build -DCMAKE_BUILD_TYPE=Release \
    && cmake --build build -j"$(nproc)" --target risk_engine_server

FROM debian:bookworm-slim AS runtime
WORKDIR /app

# Pulls in the -dev packages (not just the runtime .so packages) because their exact
# versioned names drift across Debian releases; correctness here matters more than image size.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgrpc++-dev \
    libprotobuf-dev \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /src/build/risk_engine_server ./risk_engine_server

ENV RISK_ENGINE_PORT=50051
EXPOSE 50051
CMD ["./risk_engine_server"]
