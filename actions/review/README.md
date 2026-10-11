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
    steps:
      - uses: steph-dove/klaussy-agents/actions/review@main
        with:
          anthropic-api-key: ${{ secrets.ANTHROPIC_API_KEY }}
```

On a Claude Pro or Max plan, use `claude-code-oauth-token: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}` instead, with a token from `claude setup-token`.

## Inputs

| Input | Default | |
|---|---|---|
| `anthropic-api-key` | | Anthropic API key. This or `claude-code-oauth-token` is required. |
| `claude-code-oauth-token` | | Claude Code OAuth token, instead of an API key. |
| `model` | `claude-opus-5-5` | Model the review runs on. |
| `include-nits` | `false` | Also report Warn and Nit findings. Blocker through Low are always reported. |
| `event` | `COMMENT` | `COMMENT`, or `REQUEST_CHANGES` to block merging on findings. |
| `enrich` | `true` | When the repo has no `CLAUDE.md`, enrich the generated one with Claude. |
| `max-budget-usd` | `10` | Spending cap for one review. |
| `github-token` | `github.token` | Token used to post the review. |

A review typically costs $1 to $4 in API usage on Opus, and about a third of that on `claude-sonnet-5-5`.

## How it works

1. Checks out the pull request head with full history.
2. If the repo has no `CLAUDE.md`, runs `klaussy init` to generate one from the codebase; either way it renders the review skill with this version of klaussy.
3. Runs the review skill headless in Claude Code.
4. Posts the findings: each one on the diff line it's about, anything outside the diff in the review body, with the verdict and test coverage on top.

## Security

- **Fork pull requests are skipped.** With the `pull_request` trigger, GitHub gives fork workflows no secrets, so the review finds no credential and exits with a notice. Don't switch to `pull_request_target` to get around this: that runs with your secrets on code anyone can submit.
- **The reviewer is read-only.** Claude Code runs with an allowlist of read-only commands (`git diff`, `git log`, `grep` and similar), can write nothing but `REVIEW_OUTPUT.md`, has web access and hooks turned off, and never sees the GitHub token. Only the final step, which posts the review, can write to the pull request.
- The checkout drops the pull request's `.claude/settings.json`, so a pull request can't add hooks or permissions to its own review.
