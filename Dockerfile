FROM python:3.9-slim

WORKDIR /app

# Install dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements file from the new location
COPY zulip_bots/zulip_bots/bots/standup/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy bot code
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Expose port for the bot server
EXPOSE 5002

# Command to run the bot server
# Use environment variables for configuration
CMD ["zulip-botserver", "--use-env-vars", "--bot-name", "standup", "--port", "5002"]
