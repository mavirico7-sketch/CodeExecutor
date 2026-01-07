# Python Basic Environment
FROM python:3.11-slim

# Create non-root user
RUN groupadd -r executor && useradd -r -g executor executor

# Install common packages
RUN pip install --no-cache-dir \
    requests==2.31.0 \
    pytest==8.0.0

# Create workspace directory
RUN mkdir -p /workspace && chown executor:executor /workspace

# Set working directory
WORKDIR /workspace

# Switch to non-root user
USER executor

# Default command (will be overridden)
CMD ["sleep", "infinity"]

