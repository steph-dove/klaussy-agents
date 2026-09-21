# Waiting without burning usage

Read this at Phase 7. Waiting is where this skill can spend the most for nothing: every status you check yourself costs a full turn that re-reads the whole conversation. The rule is **one wake-up per event**.

- **Put the wait inside one shell command.** It polls and sleeps on its own, prints nothing while it waits, and exits once — when the event happens or the window closes. Never poll by re-running a status command turn after turn.
- **Keep its output to the final state.** Watch modes redraw on every refresh and all of that comes back to you. Send the watch output to the null device (`/dev/null`; `$null` in PowerShell, `NUL` in cmd), then print the final status once.
- **Background it if your agent can wake you on exit.** In Claude Code, run it with Bash `run_in_background` and do nothing until the exit notification arrives. Don't check on it in between, and don't use a tool that streams every output line back to you. Without that, run it in the foreground with a long timeout, splitting the window into chunks if the timeout is shorter than the wait.

## Waiting for CI (Phase 7)

Use the adapter's watch mode where it has one:

```
gh pr checks <n> --watch --fail-fast --interval 60 > /dev/null; gh pr checks <n>
glab ci status --live > /dev/null; glab ci status
```

Swap the null device for the shell you're in. Where the host has no watch mode, wrap the adapter's CI status call in a shell loop that sleeps a minute between checks and exits on a terminal state.

## Waiting for review (Phase 8)

Write one shell loop that records how many reviews and comments the request has (the read commands are in the **`fastapi-address-review`** skill's forge section), re-counts every few minutes, and exits the first time a count changes or when the window closes. Print only the before and after counts.

**Bounded wait.** Reviews depend on a human showing up, so don't wait forever. If the window (about 30 minutes) closes with no new activity, or the user says to wrap up, stop and hand back with a summary. Resume when they say review has landed.
