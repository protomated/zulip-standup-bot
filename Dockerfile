FROM python:3.12.6-slim

WORKDIR /app

# Install git for cloning repositories during pip install
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

# Copy the entire project first
COPY . .

# Create a temporary requirements file without editable installs
RUN grep -v "^-e " requirements.txt > requirements_no_editable.txt

# Install dependencies excluding editable packages
RUN pip install --no-cache-dir -r requirements_no_editable.txt

# Install the packages in development mode
RUN pip install -e ./zulip
RUN pip install -e ./zulip_bots
RUN pip install -e ./zulip_botserver

# Install bot-specific requirements (similar to tools/provision)
RUN for req_file in $(find zulip_bots/zulip_bots/bots -name "requirements.txt"); do \
    pip install --no-cache-dir -r $req_file; \
    done

# Expose the default port
EXPOSE 5002

# Set the command to run the botserver
CMD ["zulip-botserver", "--use-env-vars", "--port", "5002", "--host", "0.0.0.0"]
