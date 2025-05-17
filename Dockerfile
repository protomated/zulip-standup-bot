FROM python:3.9-slim

WORKDIR /app

# Install system dependencies including PostgreSQL client
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create a non-root user to run the application
RUN useradd -m botuser
USER botuser

# Command to run the application
CMD ["python", "run_bot.py"]
