# ReviewBench image: `klaussy review --headless`, the hosted App's runner; see
# benchmarks/reviewbench_agent.py. Build with --platform linux/amd64.
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

# Runs have no package index; skip klaussy init's conventions upgrade attempt. ReviewBench only
# lets the model host through, so Claude Code's telemetry and update checks stay off everywhere,
# enrichment included. npm, npx and corepack stay offline: a refused registry once drew 1.4M
# retries in one round. Enrichment runs Claude outside the review runner, so the 5-minute cache
# is set here too.
ENV PATH=/opt/klaussy/bin:$PATH PIP_NO_INDEX=1 CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1 \
    DISABLE_AUTOUPDATER=1 NPM_CONFIG_OFFLINE=true COREPACK_ENABLE_NETWORK=0 \
    FORCE_PROMPT_CACHING_5M=1

WORKDIR /agent
COPY benchmarks/reviewbench_agent.py ./
ENTRYPOINT ["python3", "/agent/reviewbench_agent.py"]
