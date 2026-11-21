# Gate 1 sandbox for r8 (Java -> Rust): the standard agent image plus a pinned
# Rust toolchain. Everything else (Claude Code, opencode, Java 17 and Java 8,
# Maven, PostgreSQL 17) is the base image's, so r8 runs on the same harness.
# Crates come from crates.io through the allowlist proxy (docker/egress).
#   docker build -t gate1-agent-rust:1.100.0 docker/agent-rust
ARG BASE=gate1-agent:latest
FROM rust:1.100.0-slim-bookworm AS rust
FROM ${BASE}
RUN apt-get update && apt-get install -y --no-install-recommends gcc libc6-dev pkg-config \
    && rm -rf /var/lib/apt/lists/*
COPY --from=rust /usr/local/rustup /usr/local/rustup
COPY --from=rust /usr/local/cargo /usr/local/cargo
# the toolchain is read-only; the agent's crate cache and build state are its own
ENV RUSTUP_HOME=/usr/local/rustup CARGO_HOME=/home/agent/.cargo \
    PATH=/usr/local/cargo/bin:$PATH
RUN install -d -o agent /home/agent/.cargo \
    && rustc --version && cargo --version
LABEL gate1.rust.version=1.100.0
