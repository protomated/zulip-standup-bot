FROM python:3.11-slim

WORKDIR /app

# Install uv package manager (pinned version for stability)
COPY --from=ghcr.io/astral-sh/uv:0.7.5 /uv /bin/uv

# Set environment variables for optimized uv performance
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

# Create virtual environment
RUN uv venv /app/.venv

# Copy pyproject.toml (and uv.lock if you have it)
COPY pyproject.toml ./
COPY uv.lock* ./

# Install dependencies using uv directly from pyproject.toml
#RUN #uv pip install --no-cache-dir .
RUN uv sync --all-groups


# Copy application code
COPY . .

# Create a non-root user to run the application
RUN useradd -m botuser

# Create backups and logs directories and set permissions
RUN mkdir -p ./backups ./logs && chown -R botuser:botuser ./backups ./logs

# Declare volumes for persistent data
VOLUME ["/app/backups"]

USER botuser

# Command to run the application using uv run instead of python directly
CMD ["uv", "run", "run_bot.py"]
