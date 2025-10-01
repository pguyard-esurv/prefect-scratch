# RPA3 Flow Container Image
# Built from base image with flow-specific configuration

ARG BASE_IMAGE=rpa-base:latest
FROM ${BASE_IMAGE}

# Set flow-specific metadata
LABEL flow.name="rpa3" \
      flow.description="RPA3: Concurrent data processing demo workflow" \
      flow.version="1.0.0"

# Set flow-specific environment variables
ENV FLOW_NAME=rpa3 \
    FLOW_TYPE=concurrent_processing \
    PREFECT_FLOW_NAME=rpa3-concurrent-processing

# Copy flow-specific code
COPY flows/rpa3/ ./flows/rpa3/

# Copy flow-specific startup script
COPY scripts/flow_startup.sh ./scripts/
COPY scripts/container_lifecycle_startup.py ./scripts/

# Switch to root to set permissions, then back to non-root user
USER root
RUN chmod +x ./scripts/flow_startup.sh ./scripts/container_lifecycle_startup.py

# Create flow-specific directories with proper permissions
RUN mkdir -p /app/flows/rpa3/data /app/flows/rpa3/output && \
    chown -R rpauser:rpauser /app/flows/rpa3

USER rpauser

# Flow-specific health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD uv run python ../../scripts/health_check.py --flow=rpa3 || exit 1

# Set working directory to flow
WORKDIR /app/flows/rpa3

# Default command runs the enhanced lifecycle startup script
CMD ["uv", "run", "python", "../../scripts/container_lifecycle_startup.py", "--flow-name", "rpa3", "--mode", "managed"]