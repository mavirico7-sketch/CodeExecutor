# Python ML Environment
FROM python:3.11-slim

# Install system dependencies for ML libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r executor && useradd -r -g executor executor

# Install ML packages
RUN pip install --no-cache-dir \
    numpy==1.26.3 \
    pandas==2.2.0 \
    scikit-learn==1.4.0 \
    matplotlib==3.8.2 \
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

