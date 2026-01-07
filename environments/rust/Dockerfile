# Rust Environment
FROM rust:1.75-slim

# Create non-root user
RUN groupadd -r executor && useradd -r -g executor executor

# Create workspace directory
RUN mkdir -p /workspace && chown executor:executor /workspace

# Set working directory
WORKDIR /workspace

# Switch to non-root user
USER executor

# Default command (will be overridden)
CMD ["sleep", "infinity"]

