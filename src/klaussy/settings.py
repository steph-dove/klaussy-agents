"""Generate .claude/settings.json with stack-appropriate defaults."""

import json
from pathlib import Path

from rich.console import Console

console = Console()


def _detect_stack(repo: Path) -> dict[str, bool]:
    """Detect project stack from common marker files."""
    return {
        "python": (repo / "pyproject.toml").exists() or (repo / "setup.py").exists(),
        "node": (repo / "package.json").exists(),
        "go": (repo / "go.mod").exists(),
        "rust": (repo / "Cargo.toml").exists(),
        "make": (repo / "Makefile").exists(),
    }


def _build_allowed_tools(stack: dict[str, bool]) -> list[str]:
    """Build allowedTools list based on detected stack."""
    tools: list[str] = [
        "Read",
        "Edit",
        "Write",
        "Glob",
        "Grep",
        "Bash(git *)",
    ]

    if stack["python"]:
        tools.extend([
            "Bash(python *)",
            "Bash(pytest *)",
            "Bash(ruff *)",
            "Bash(mypy *)",
            "Bash(pip *)",
            "Bash(uv *)",
        ])
    if stack["node"]:
        tools.extend([
            "Bash(npm *)",
            "Bash(npx *)",
            "Bash(node *)",
            "Bash(yarn *)",
            "Bash(pnpm *)",
        ])
    if stack["go"]:
        tools.extend([
            "Bash(go *)",
        ])
    if stack["rust"]:
        tools.extend([
            "Bash(cargo *)",
        ])
    if stack["make"]:
        tools.append("Bash(make *)")

    return tools


SENSITIVE_PATTERNS = [
    ".env",
    ".env.*",
    "credentials*",
    "secrets*",
    "*.pem",
    "*.key",
    "**/service-account*.json",
]


def _detect_sensitive_paths(repo: Path) -> list[str]:
    """Find sensitive files/dirs that should be denied."""
    deny: list[str] = []
    for pattern in SENSITIVE_PATTERNS:
        matches = list(repo.glob(pattern))
        if matches:
            deny.append(f"Read({pattern})")
            deny.append(f"Edit({pattern})")
    return deny


def generate_settings(*, repo: Path, force: bool = False) -> Path:
    """Generate .claude/settings.json."""
    repo = repo.resolve()
    settings_file = repo / ".claude" / "settings.json"

    if settings_file.exists() and not force:
        console.print(
            f"[yellow]⚠ {settings_file.relative_to(repo)} already exists. "
            "Use --force to overwrite.[/yellow]"
        )
        raise SystemExit(1)

    stack = _detect_stack(repo)
    allowed_tools = _build_allowed_tools(stack)
    deny_rules = _detect_sensitive_paths(repo)

    detected = [name for name, found in stack.items() if found]
    console.print(f"[dim]Detected stack: {', '.join(detected) or 'none'}[/dim]")
    if deny_rules:
        console.print(f"[dim]Denied sensitive paths: {len(deny_rules) // 2} patterns[/dim]")

    settings = {
        "permissions": {
            "allow": allowed_tools,
            "deny": deny_rules,
        },
    }

    settings_file.parent.mkdir(parents=True, exist_ok=True)
    settings_file.write_text(json.dumps(settings, indent=2) + "\n")
    console.print(f"[green]✔ Created {settings_file.relative_to(repo)}[/green]")
    return settings_file
