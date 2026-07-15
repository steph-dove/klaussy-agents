"""Scaffold .claude/skills/ with namespaced Claude Code skills."""

import re
from importlib import resources
from pathlib import Path

from rich.console import Console

from klaussy import __version__

console = Console()

SKILL_NAMES = [
    "review",
    "precommit",
    "plan",
    "debug",
    "implement",
    "refactor",
    "test",
    "run",
    "qa",
    "self-review",
    "fix",
    "pr",
    "commit",
    "explain",
    "humanize",
    "document",
    "deps",
    "release",
    "address-review",
    "new-worktree",
    "adr-generator",
    "security-audit",
    "slop-coded",
    "rest-of-the-owl",
]

VERSION_FILE = ".klaussy-version"

# Shared "write like a human" block, substituted into prose-output skills via
# the {{HUMANIZE}} token. This is the prompt-side mirror of klaussy-desktop's
# deterministic humanizer (main/util/humanize-comment.js) — keep the two in sync
# so an agent's output and the desktop post-processor agree on what reads human.
HUMANIZE_BLOCK = "\n".join(
    [
        "### Write like a person, not a chatbot",
        "",
        "Whatever you output for the user (comments, descriptions, messages) must"
        " read as if a human engineer wrote it. These rules mirror klaussy's"
        " deterministic humanizer (klaussy-desktop `humanize-comment.js`):",
        "",
        "- **No em-dashes or en-dashes** (`—` / `–`) in prose. Use a comma"
        " or rewrite. This is the single biggest AI tell.",
        '- **No filler openers.** Cut "It\'s worth noting that", "It\'s important to'
        ' note that", "I noticed that", "I wanted to point out that", "Please'
        ' note that", "Just to mention", "Worth noting", "Note that". State'
        " the point directly.",
        '- **No chatbot scaffolding.** No "Let me know if...", "Hope this helps",'
        ' "Feel free to...", "Happy to help", "Let me know your thoughts".',
        '- **Tighten hedges.** "in order to" → "to"; "could potentially"'
        ' → "could"; "may potentially" → "may". Drop stacked'
        " qualifiers.",
        '- **No emoji, no exclamatory enthusiasm, no "Certainly"/"Great question".**',
        "- **Don't let trimming tip into terse.** Cutting filler shouldn't make"
        " prose read as curt or dismissive. Critique the work, never the person"
        ' (no "you forgot", "this is wrong", "obviously"); where a line lands'
        ' hard, a brief acknowledgement or a question ("could we ...?", "one'
        ' risk is ...") takes the edge off. A light touch only, not filler praise'
        ' or "great job" boilerplate.',
        "- **No superlatives or ranking praise.** Don't editorialize a point's"
        ' importance: cut "this is the sharpest catch in the review", "best'
        ' catch", "great find", "excellent point", "the most important issue'
        ' here". Rating a comment against the others is an AI tell and adds'
        " nothing. State the substance and stop.",
        "- **Don't mirror the thread's tone.** When you reply to an existing"
        " comment, review note, or message, read it for substance but not for"
        " temperature: neutralize any rudeness or bluntness in it before you"
        " draft. Hostile or curt input must not prime a hostile or curt reply,"
        " answer as if the other person had phrased it civilly.",
        "- **Don't thank a bot.** When the reviewer is an automated tool or bot"
        " (a review bot, another agent, a CI check), respond to the substance"
        " without gratitude or pleasantries aimed at it, no \"thanks for the"
        ' review", "good catch", or addressing it as a person. Reserve those'
        " for a human reviewer, and even then keep them minimal.",
        "- **Be short, then cut more.** Lead with the point. Keep the decision and"
        " the one fact that justifies it, then stop. A reply in a thread is usually"
        " one sentence; a single review comment one to five. Don't pad to sound"
        " thorough or stack throat-clearing ahead of the point.",
        "- **Cut detail, not just words.** The verbose tell isn't long words, it's"
        " over-explaining. Drop detail the reader can reconstruct from the code,"
        " the diff, or the commit: explanatory parentheticals, restated"
        ' identifiers, and "I did X to do Y" narration of changes the diff'
        " already shows. Keep the load-bearing fact; drop what's merely supporting."
        " This is the one place humanizing may drop content, never reverse or"
        " invent meaning, but you need not preserve every clause.",
        "- Vary sentence shape; don't open every line the same way. Never reword"
        " code, identifiers, or anything inside backticks or fences. Humanize prose"
        " only.",
        "",
        "**Same decision, half the words, dropping detail the reader can reconstruct:**",
        "",
        "> Verbose: Good call, done. attachment.reason already embeds the decline"
        " reason for declined envelopes (built in checkEnvelopeStatus as {name}"
        " declined on {date} - {declinedReason}), so I dropped the new"
        " declinedReason signer field and reverted NotificationService to use the"
        " existing reason field. Pushed in 1e9e938404.",
        "",
        "> Human: Good call. `attachment.reason` already carries the decline"
        " reason, so I dropped the new field and reverted NotificationService."
        " Pushed in 1e9e938404.",
    ]
)

# Filenames generated by previous klaussy versions (<0.2.0) that scaffolded
# .claude/commands/. Listed explicitly so we only remove files we created and
# leave any user-authored commands alone.
LEGACY_COMMAND_FILENAMES = [
    "test.md",
    "fix.md",
    "pr.md",
    "commit.md",
    "debug.md",
    "explain.md",
    "implement.md",
    "refactor.md",
    "new-worktree.md",
    # review was scoped: pr-review-<repo>.md
]


def sanitize_skill_namespace(name: str) -> str:
    """Coerce a string into the kebab-case form Claude Code requires for skill names.

    The skill `name` field accepts only `[a-z0-9-]+`. Repo basenames in the
    wild can be uppercase, snake_case, or contain dots/spaces; passing them
    through verbatim would produce skills Claude Code refuses to load. Apply
    a deterministic normalization: lowercase, swap any non-alphanumeric run
    for a single hyphen, trim leading/trailing hyphens. Falls back to
    "repo" for the degenerate empty-after-sanitization case.
    """
    cleaned = re.sub(r"[^a-z0-9-]+", "-", name.lower())
    cleaned = re.sub(r"-+", "-", cleaned).strip("-")
    return cleaned or "repo"


def _skill_dir_name(repo: Path, skill: str) -> str:
    """Return the namespaced skill directory name (e.g., 'myapp-plan')."""
    return f"{sanitize_skill_namespace(repo.name)}-{skill}"


def _read_version(marker_dir: Path) -> str | None:
    """Read the klaussy version from a marker file in marker_dir."""
    version_path = marker_dir / VERSION_FILE
    if version_path.exists():
        return version_path.read_text().strip()
    return None


def _write_version(marker_dir: Path) -> None:
    """Write the current klaussy version to the marker file."""
    (marker_dir / VERSION_FILE).write_text(__version__ + "\n")


def _migrate_legacy_commands(repo: Path) -> None:
    """Remove .claude/commands/ files generated by older klaussy versions."""
    commands_dir = repo / ".claude" / "commands"
    legacy_marker = commands_dir / VERSION_FILE
    if not legacy_marker.exists():
        return

    removed: list[Path] = []
    for filename in LEGACY_COMMAND_FILENAMES:
        target = commands_dir / filename
        if target.exists():
            target.unlink()
            removed.append(target)

    legacy_review = commands_dir / f"pr-review-{repo.name}.md"
    if legacy_review.exists():
        legacy_review.unlink()
        removed.append(legacy_review)

    legacy_marker.unlink()

    try:
        commands_dir.rmdir()
    except OSError:
        pass

    for path in removed:
        console.print(f"[dim]  Removed legacy {path.relative_to(repo)}[/dim]")
    console.print(f"[green]✔ Migrated {len(removed)} legacy command(s) → skills.[/green]")


def scaffold_skills(
    *,
    repo: Path,
    force: bool = False,
    review_template: Path | None = None,
    base_branch: str = "main",
) -> list[Path]:
    """Create .claude/skills/<repo>-<skill>/SKILL.md for each shipped skill."""
    repo = repo.resolve()
    skills_dir = repo / ".claude" / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)

    _migrate_legacy_commands(repo)

    existing_version = _read_version(skills_dir)
    if existing_version == __version__ and not force:
        console.print(f"[dim]Skills already up to date (v{__version__}), skipping.[/dim]")
        return []

    created: list[Path] = []
    templates = resources.files("klaussy").joinpath("templates/skills")

    repo_namespace = sanitize_skill_namespace(repo.name)

    def _substitute(text: str) -> str:
        return (
            text.replace("{{REPO}}", repo_namespace)
            .replace("{{BASE_BRANCH}}", base_branch)
            .replace("{{HUMANIZE}}", HUMANIZE_BLOCK)
        )

    for skill in SKILL_NAMES:
        skill_dir = skills_dir / _skill_dir_name(repo, skill)
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_template_dir = templates.joinpath(skill)

        # Copy every template file in the skill dir. Skills like `review` ship
        # supporting files (e.g. sub-agents.md) alongside SKILL.md and need
        # them all written for the skill to function.
        for template_file in skill_template_dir.iterdir():
            filename = template_file.name
            target = skill_dir / filename

            # The review skill alone supports a custom SKILL.md override (since
            # it also receives repo-specific check enrichment via `klaussy
            # checklist`). Sibling files like sub-agents.md still come from the
            # built-in templates.
            if skill == "review" and filename == "SKILL.md" and review_template is not None:
                content = review_template.read_text()
            else:
                content = template_file.read_text()

            content = _substitute(content)

            if target.exists() and target.read_text() == content and not force:
                console.print(f"[dim]  {target.relative_to(repo)} unchanged, skipping.[/dim]")
                continue

            target.write_text(content)
            created.append(target)
            console.print(f"[green]✔ Created {target.relative_to(repo)}[/green]")

    _write_version(skills_dir)

    if not created:
        console.print("[dim]No skill files created.[/dim]")

    return created
