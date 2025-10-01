# RPA2 Flow Container Image
# Built from base image with flow-specific configuration

ARG BASE_IMAGE=rpa-base:latest
FROM ${BASE_IMAGE}

# Set flow-specific metadata
LABEL flow.name="rpa2" \
      flow.description="RPA2: Data validation and reporting workflow" \
      flow.version="1.0.0"

# Set flow-specific environment variables
ENV FLOW_NAME=rpa2 \
    FLOW_TYPE=validation \
    PREFECT_FLOW_NAME=rpa2-validation

# Copy flow-specific code
COPY flows/rpa2/ ./flows/rpa2/

# Copy flow-specific startup script
COPY scripts/flow_startup.sh ./scripts/
COPY scripts/container_lifecycle_startup.py ./scripts/

# Switch to root to set permissions, then back to non-root user
USER root
RUN chmod +x ./scripts/flow_startup.sh ./scripts/container_lifecycle_startup.py

# Create flow-specific directories with proper permissions
RUN mkdir -p /app/flows/rpa2/data /app/flows/rpa2/output && \
    chown -R rpauser:rpauser /app/flows/rpa2

USER rpauser

# Flow-specific health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD uv run python ../../scripts/health_check.py --flow=rpa2 || exit 1

# Set working directory to flow
WORKDIR /app/flows/rpa2

# Default command runs the enhanced lifecycle startup script
CMD ["uv", "run", "python", "../../scripts/container_lifecycle_startup.py", "--flow-name", "rpa2", "--mode", "managed"]