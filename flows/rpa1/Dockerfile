FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Copy only the necessary files
COPY flows/rpa1 /app/flows/rpa1
COPY core /app/core
COPY pyproject.toml /app/
COPY README.md /app/

# Install uv for faster package installation
RUN pip install --no-cache-dir uv

# Create virtual environment and install dependencies
RUN uv venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
RUN uv pip install -e .
RUN uv pip install "prefect-docker>=0.3.1"

# Set environment variables
ENV PREFECT_API_URL=http://prefect-server:4200/api
ENV PYTHONPATH=/app
ENV PREFECT_CLIENT_CONNECT_URL=http://prefect-server:4200/api
ENV PREFECT_SERVER_API_HOST=prefect-server
ENV PREFECT_SERVER_API_PORT=4200

# Command to run the flow
CMD ["prefect", "flow", "serve", "flows/rpa1/workflow.py:rpa1_workflow"]