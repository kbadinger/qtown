# ─── Stage 1: Build ───────────────────────────────────────────────────────────
#
# Use the official Rust slim image as the build base.
# We install only the minimal system dependencies needed for rdkafka's
# cmake-build feature (libssl, cmake, clang) and then compile a release binary.

FROM rust:1.79-slim AS builder

# System deps for rdkafka cmake-build and OpenSSL.
RUN apt-get update && apt-get install -y --no-install-recommends \
    cmake \
    clang \
    libssl-dev \
    pkg-config \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# ── Dependency caching layer ──────────────────────────────────────────────────
# Copy manifests first so that `cargo fetch` / `cargo build --release` caches
# the compiled dependencies separately from application source changes.
COPY Cargo.toml Cargo.lock* ./

# Create a stub lib.rs and main.rs so `cargo build` can resolve all deps
# without requiring the full source tree.
RUN mkdir -p src/validation benches \
    && echo 'pub mod types; pub mod validation; pub mod wasm_sandbox;' > src/lib.rs \
    && echo 'fn main() {}' > src/main.rs \
    && touch src/types.rs src/wasm_sandbox.rs \
    && echo 'pub mod rules;' > src/validation/mod.rs \
    && touch src/validation/rules.rs \
    && echo 'fn main() {}' > benches/validation.rs \
    && cargo build --release 2>&1 \
    && rm -rf src benches

# ── Application source ────────────────────────────────────────────────────────
COPY src ./src
COPY benches ./benches

# Touch main.rs to force a rebuild after the stub replacement.
RUN touch src/main.rs \
    && cargo build --release

# ─── Stage 2: Runtime ─────────────────────────────────────────────────────────
#
# Use a minimal Debian image. No Rust toolchain — just the compiled binary
# and the shared libraries it links against at runtime.

FROM debian:bookworm-slim AS runtime

# Install shared libraries required at runtime.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libssl3 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Run as a non-root user for defence in depth.
RUN useradd --no-create-home --shell /bin/false fortress
USER fortress

# Copy the statically-linked binary from the build stage.
COPY --from=builder /build/target/release/fortress /usr/local/bin/fortress

# ── Ports ─────────────────────────────────────────────────────────────────────
# 50052 — Tonic gRPC (validation RPC endpoint)
# 8080  — HTTP health / readiness probes
EXPOSE 50052 8080

# ── Healthcheck ───────────────────────────────────────────────────────────────
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -sf http://localhost:8080/healthz || exit 1

ENTRYPOINT ["/usr/local/bin/fortress"]
