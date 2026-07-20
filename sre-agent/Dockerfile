FROM python:3.11-slim

# Install kubectl + AWS CLI v2 + Argo CD CLI + Bitbucket CLI + GitHub CLI for the build's target architecture.
# kubectl is used by the infrastructure-kubernetes skill.
# AWS CLI is needed for EKS exec auth (~/.kube/config runs `aws eks get-token`)
# and so boto3 SSO credential refresh works from inside the container.
# argocd is used by the platform-argocd skill (app sync/get/history/logs/diff).
# bkt is used by the vcs-bitbucket skill.
# gh is used by the vcs-github skill.
# TARGETARCH is auto-set by BuildKit (arm64 on Apple Silicon, amd64 elsewhere);
# binaries MUST match the base image arch, otherwise Rosetta fails with
# "failed to open elf at /lib64/ld-linux-x86-64.so.2" on Apple Silicon.
ARG TARGETARCH
ARG ARGOCD_VERSION=v3.4.4
ARG BKT_VERSION=0.28.2
ARG GH_VERSION=2.96.0
# Split downloads so flaky networks can resume from cached layers; curl retries on transient failures.
RUN apt-get update && \
    apt-get install -y curl unzip && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*
RUN KUBECTL_ARCH=$([ "$TARGETARCH" = "arm64" ] && echo arm64 || echo amd64) && \
    curl -fSL --retry 5 --retry-delay 5 --retry-all-errors \
      -LO "https://dl.k8s.io/release/$(curl -fsSL --retry 5 https://dl.k8s.io/release/stable.txt)/bin/linux/${KUBECTL_ARCH}/kubectl" && \
    install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl && \
    rm kubectl
RUN AWS_ARCH=$([ "$TARGETARCH" = "arm64" ] && echo aarch64 || echo x86_64) && \
    curl -fSL --retry 5 --retry-delay 5 --retry-all-errors \
      "https://awscli.amazonaws.com/awscli-exe-linux-${AWS_ARCH}.zip" -o awscliv2.zip && \
    unzip -q awscliv2.zip && \
    ./aws/install && \
    rm -rf aws awscliv2.zip
RUN ARGOCD_ARCH=$([ "$TARGETARCH" = "arm64" ] && echo arm64 || echo amd64) && \
    curl -fSL --retry 5 --retry-delay 5 --retry-all-errors \
      -o /usr/local/bin/argocd \
      "https://github.com/argoproj/argo-cd/releases/download/${ARGOCD_VERSION}/argocd-linux-${ARGOCD_ARCH}" && \
    chmod 555 /usr/local/bin/argocd
RUN BKT_ARCH=$([ "$TARGETARCH" = "arm64" ] && echo arm64 || echo x86_64) && \
    curl -fSL --retry 5 --retry-delay 5 --retry-all-errors \
      -o /tmp/bkt.tgz \
      "https://github.com/avivsinai/bitbucket-cli/releases/download/v${BKT_VERSION}/bkt_${BKT_VERSION}_linux_${BKT_ARCH}.tar.gz" && \
    tar -xzf /tmp/bkt.tgz -C /usr/local/bin bkt && \
    chmod 555 /usr/local/bin/bkt && \
    rm /tmp/bkt.tgz
RUN GH_ARCH=$([ "$TARGETARCH" = "arm64" ] && echo arm64 || echo amd64) && \
    curl -fSL --retry 5 --retry-delay 5 --retry-all-errors \
      -o /tmp/gh.tgz \
      "https://github.com/cli/cli/releases/download/v${GH_VERSION}/gh_${GH_VERSION}_linux_${GH_ARCH}.tar.gz" && \
    tar -xzf /tmp/gh.tgz -C /tmp && \
    install -o root -g root -m 0555 "/tmp/gh_${GH_VERSION}_linux_${GH_ARCH}/bin/gh" /usr/local/bin/gh && \
    rm -rf /tmp/gh.tgz "/tmp/gh_${GH_VERSION}_linux_${GH_ARCH}"

WORKDIR /app

# Install uv for fast package management
RUN pip install --no-cache-dir uv

# Copy dependency files first (layer cache for deps)
COPY pyproject.toml .

# Install dependencies (non-editable; source files are not present yet)
RUN uv pip install --system --no-cache-dir .

# Copy all application source
COPY agent.py server.py server_simple.py config.py events.py auth.py \
     report.py sandbox_manager.py sandbox_server.py message_queue.py \
     investigation_lifecycle.py team_context.py tool_output_sanitize.py ./
COPY memory/ memory/
COPY tools/ tools/
COPY .claude/ .claude/
COPY sandbox-router/ sandbox-router/

# Create non-root user
RUN useradd -m -u 1000 agent && \
    mkdir -p /data/agent-sessions && \
    chown -R agent:agent /app /data/agent-sessions

USER agent

# Expose port
EXPOSE 8000

# Run simple server (SDK engine)
CMD ["python", "server_simple.py"]
