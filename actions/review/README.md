# klaussy review

Multi-agent code review on every pull request, run on your repo's own conventions. Specialist reviewers each take one angle (correctness twice, architecture, security, scope), a validator checks every finding against the code before it ships, and the result is posted as a pull request review with comments on the lines they're about.

## Usage

Add an `ANTHROPIC_API_KEY` repository secret, then `.github/workflows/klaussy-review.yml`:

```yaml
name: klaussy review

on:
  pull_request:
    types: [opened, synchronize, ready_for_review]

permissions:
  contents: read
  pull-requests: write

concurrency:
  group: klaussy-review-${{ github.event.pull_request.number }}
  cancel-in-progress: true

jobs:
  review:
    if: ${{ !github.event.pull_request.draft }}
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - uses: steph-dove/klaussy-agents/actions/review@main
        with:
          anthropic-api-key: ${{ secrets.ANTHROPIC_API_KEY }}
```

On a Claude Pro or Max plan, use `claude-code-oauth-token: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}` instead, with a token from `claude setup-token`.

To review with GitHub Copilot instead, create a fine-grained personal access token with only the **Copilot Requests** permission, from an account with a Copilot license, and store it as a secret:

```yaml
      - uses: steph-dove/klaussy-agents/actions/review@main
        with:
          agent: copilot
          copilot-github-token: ${{ secrets.COPILOT_GITHUB_TOKEN }}
```

**OpenAI models are in preview:** they haven't passed a live run yet. `agent: openai` runs Copilot CLI with your OpenAI key as its model provider, so it gets the same restrictions as `agent: copilot` and needs no Copilot license. Store an OpenAI API key as a secret:

```yaml
      - uses: steph-dove/klaussy-agents/actions/review@main
        with:
          agent: openai
          openai-api-key: ${{ secrets.OPENAI_API_KEY }}
```

## Inputs

| Input | Default | |
|---|---|---|
| `agent` | `claude` | `claude`, `copilot`, or `openai` (Copilot CLI on your OpenAI key). |
| `anthropic-api-key` | | Anthropic API key. With `agent: claude`, this or `claude-code-oauth-token` is required. |
| `claude-code-oauth-token` | | Claude Code OAuth token, instead of an API key. |
| `copilot-github-token` | | Fine-grained token with the Copilot Requests permission. Required with `agent: copilot`. |
| `openai-api-key` | | OpenAI API key. Required with `agent: openai`. |
| `model` | | Model the review runs on. Defaults to `claude-opus-5-5` for Claude, `gpt-5.4` for OpenAI, and Copilot's own default for Copilot. |
| `include-nits` | `false` | Also report Warn and Nit findings. Blocker through Low are always reported. |
| `event` | `COMMENT` | `COMMENT`, `REQUEST_CHANGES` to block merging on findings, or `APPROVE`. |
| `enrich` | `false` | When the base branch has no `CLAUDE.md`, enrich the generated one with Claude (Claude only). This runs Claude over the pull request's code a second time, without the review's restrictions. |
| `max-budget-usd` | `20` | Spending cap for one review (Claude). An Opus review averages about $5 and can reach $15. |
| `max-ai-credits` | | AI credit cap for one review (Copilot). Empty means no cap. |
| `github-token` | `github.token` | Token used to post the review. |
| `claude-code-version` | `2.1.296` | Claude Code CLI version to install. |
| `copilot-version` | `1.0.95` | GitHub Copilot CLI version to install. |

On Opus a review averages about $5 in API usage and can reach $15, which is why `max-budget-usd` defaults to 20.

## How it works

1. Checks out the pull request head with full history.
2. Runs `klaussy review --headless`, the same runner the hosted klaussy review App uses. It removes the pull request's own agent config, takes conventions from the base branch, generates a `CLAUDE.md` if the repo has none, renders the review skill for the chosen agent, and runs it headless in Claude Code or Copilot CLI.
3. Posts the findings: each one on the diff line it's about, anything outside the diff in the review body, with the verdict and test coverage on top. A finding reads as one line saying what's wrong and the suggested change, with the full explanation in a collapsed **Explanation** section.

## Security

- **Fork and Dependabot pull requests are skipped.** With the `pull_request` trigger, GitHub gives fork and Dependabot workflows no Actions secrets, so the review finds no credential and exits with a notice. Don't switch to `pull_request_target` to get around this: that runs with your secrets on code anyone can submit.
- **The reviewer is read-only.** The agent runs with an allowlist: the `git` commands it needs to read the pull request, `klaussy base` and `klaussy review-prep`, and writing `REVIEW_OUTPUT.md`. It has no shell commands that print files, no web access, no MCP servers and no hooks. Claude Code can't read `/proc`; Copilot, including on an OpenAI key, is held to the working directory. `git` refuses options that write files, run commands or read outside the repo (`--output`, `-c`, `-C`, `--contents`, `--no-index`, `--ext-diff` and similar), and the pull request's diff is taken before the reviewer runs, so nothing it does can change what gets posted against.
- **The reviewer never holds a token that can write.** The GitHub token is unset in the review step; only the final step, which posts the review, has it. Copilot's own token is stripped from the environment of the commands it runs.
- **A pull request can't configure its own review.** Its `.claude/` skills, agents, settings and hooks, `.github/skills`, `.github/agents`, `.github/hooks`, `.agents/`, `.codex/` and `.mcp.json`, plus `.claude` directories at any depth, are removed, and `CLAUDE.md`, `.claude/rules`, `AGENTS.md`, `GEMINI.md` and Copilot's instructions, at any depth, are taken from the base branch.
- **Credentials are scrubbed from what gets posted.** Known token shapes, and the values of the Action's credential inputs, are replaced with `[redacted]` in the review and the job summary.
