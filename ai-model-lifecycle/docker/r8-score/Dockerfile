# r8 scorer: builds, tests and runs the agent's Rust service. The same Rust
# toolchain as the sandbox (docker/agent-rust), and no JVM, so a service that
# needs Java cannot run here.
#   docker build -t gate1-r8-rust:1.100.0 docker/r8-score
FROM rust:1.100.0-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends pkg-config curl \
    && rm -rf /var/lib/apt/lists/* && ! command -v java
