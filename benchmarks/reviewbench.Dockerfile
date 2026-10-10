# ReviewBench image for the klaussy review skill; see benchmarks/reviewbench_agent.py.
# Credential: CLAUDE_CODE_OAUTH_TOKEN or ANTHROPIC_API_KEY. Egress: api.anthropic.com.
FROM node:22-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates python3 python3-venv \
    && rm -rf /var/lib/apt/lists/* \
    && npm install -g --no-audit --no-fund @anthropic-ai/claude-code@2.1.296 \
    && npm cache clean --force

COPY pyproject.toml README.md LICENSE /build/klaussy/
COPY src /build/klaussy/src
RUN python3 -m venv /opt/klaussy \
    && /opt/klaussy/bin/pip install --no-cache-dir /build/klaussy klaussy-repo-conventions \
    && rm -rf /build

# Runs have no package index; skip klaussy init's conventions upgrade attempt.
# Claude Code refuses bypassPermissions as root outside a sandbox; the
# container is the sandbox.
ENV PATH=/opt/klaussy/bin:$PATH PIP_NO_INDEX=1 IS_SANDBOX=1

WORKDIR /agent
COPY benchmarks/runner.py benchmarks/reviewbench_agent.py ./
ENTRYPOINT ["python3", "/agent/reviewbench_agent.py"]
