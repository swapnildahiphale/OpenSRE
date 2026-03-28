FROM python:3.11-slim

# Install kubectl
RUN apt-get update && \
    apt-get install -y curl && \
    curl -LO "https://dl.k8s.io/release/$(curl -sL https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" && \
    install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl && \
    rm kubectl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install uv for fast package management
RUN pip install --no-cache-dir uv

# Copy dependency files
COPY pyproject.toml .

# Install dependencies
RUN uv pip install --system -e .

# Copy application code
COPY graph.py state.py config.py events.py server.py auth.py memory_service.py ./
COPY nodes/ nodes/
COPY langgraph.json .
COPY memory/ memory/
COPY tools/ tools/
COPY .claude/ .claude/

# Create non-root user
RUN useradd -m -u 1000 agent && \
    chown -R agent:agent /app

USER agent

# Expose port
EXPOSE 8000

# Run simple server
CMD ["python", "server.py"]
