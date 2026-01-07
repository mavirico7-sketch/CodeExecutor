# Node.js Environment
FROM node:20-slim

# Create non-root user
RUN groupadd -r executor && useradd -r -g executor executor

# Install common packages globally
RUN npm install -g \
    lodash@4.17.21 \
    axios@1.6.5 \
    typescript@5.3.3 \
    ts-node@10.9.2

# Create workspace directory
RUN mkdir -p /workspace && chown executor:executor /workspace

# Set working directory
WORKDIR /workspace

# Switch to non-root user
USER executor

# Default command (will be overridden)
CMD ["sleep", "infinity"]

