"""Scaffold .claude/skills/ with namespaced Claude Code skills."""

import re
from importlib import resources
from pathlib import Path

from rich.console import Console

from klaussy import __version__
from klaussy.forge import build_forge_block

console = Console()

# Claude's own permission surface for the grant-permissions {{PERMISSIONS_TARGET}}
# sentinel — the Claude scaffold path skips render.py, so it feeds these through
# the same composer (imported lazily to avoid a skills<->render cycle).
_CLAUDE_PERMISSIONS_FILE = (
    "`.claude/settings.local.json` (personal, git-ignored) or "
    "`.claude/settings.json` (shared with the team)"
)
_CLAUDE_PERMISSION_SYNTAX = (
    "a `permissions.allow` / `permissions.deny` array of string rules like "
    "`Bash(git *)`, `Edit(**)`, and `Read(**)`"
)

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
    "restack",
    "split-pr",
    "adr-generator",
    "security-audit",
    "slop-coded",
    "rest-of-the-owl",
    "grant-permissions",
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
        "Whatever you output for a human (review comments, PR text, explanations,"
        " replies) must read like a colleague wrote it in a hurry, not like a model"
        " composed it. Two failure modes, and you have to beat both: sounding like"
        " AI, and saying more than the reader needs. These rules mirror klaussy's"
        " deterministic humanizer (klaussy-desktop `humanize-comment.js`):",
        "",
        "Before anything else: **no em-dashes or en-dashes** (`—` / `–`) in prose."
        " Use a comma or rewrite the sentence. That one tell gives the game away"
        " faster than everything below it combined.",
        "",
        "**Voice: say it out loud.**",
        "",
        "- **Write what you'd say standing at their desk.** If you wouldn't say the"
        " sentence to a colleague, don't write it. That one test catches most of"
        " what follows.",
        "- **Use contractions.** it's, doesn't, won't, that's, here's. Prose without"
        " them reads like a manual.",
        '- **Verbs, not noun phrases.** "This validates the token", not "this'
        ' performs validation of the token". "We cache it", not "caching is'
        ' applied". Turning verbs into nouns is the loudest tell after em-dashes.',
        '- **Name the thing doing the work.** "The retry loop eats the 429", not'
        ' "error handling may result in suppression of the status".',
        "- **Short common words.** *before* not *prior to*, *if* not *in the event"
        " that*, *can* not *is able to*, *about* not *regarding*, *but* not"
        " *however*, *so* not *thus*, *use* not *utilize*.",
        '- **Fragments are fine.** "Same bug two lines down." is a complete thought;'
        " don't pad it into a sentence.",
        "- **One idea per sentence.** If a sentence has two clauses joined by a"
        " comma and a *which*, it's two sentences. Short sentences are easier to"
        " read than clever ones.",
        '- **One modifier, not three.** Cut the triads ("clear, concise, and'
        ' maintainable"). Pick the word that carries the point.',
        '- **Don\'t announce structure.** No "There are three issues here:", no'
        ' "Let me walk through this". Say the thing.',
        "- **Vary sentence shape.** Don't open every line the same way, and don't"
        " land on the same length every time.",
        "",
        "**Shape: the smallest thing that carries the point.**",
        "",
        "- **Budgets.** A thread reply is one sentence. A single review comment is"
        " one to three. An explanation leads with two or three sentences that answer"
        " the question, then adds detail only where the reader can't infer it."
        " Over budget means you're saying more than the reader needs, not that you"
        " write long.",
        "- **Unrelated problems are separate comments.** Two findings that happen"
        " to sit near each other read better apart. One finding that spans a few"
        " files because the fix touches them all is still one comment, don't"
        " fracture it. The test is whether the reader would act on them separately.",
        "- **Lead with the change, not the discovery.** Your first sentence names"
        ' what to do ("set `soft_time_limit=3600` here"), not what you noticed'
        ' ("this task inherits the app-wide limits"). The reader stops as soon as'
        " they have what they need, so someone who reads one sentence should"
        " already be able to act. Why it matters comes second, the mechanism last"
        " if it earns a place at all.",
        "- **Prose by default.** No headings, tables, or bold field labels. Bullets"
        " only for a real list of three or more parallel items, never as a wrapper"
        " around one paragraph.",
        "- **Three sentences to a paragraph.** A fourth one means a second paragraph"
        " or a second comment. Put a blank line between them, a wall of text is hard"
        " to get back into after looking away.",
        "- **No bookends.** Don't open by restating the request and don't close by"
        " summarizing what you just said. Start at the point, stop when it's made.",
        "- **Don't quote what they're already looking at.** In an inline comment the"
        " code is on screen. Point at it, don't paste it back.",
        "- **No status theater.** Severity labels, confidence scores, checkbox"
        ' lists, and "Method:" footers only when the output format requires them.',
        "- **Cut detail, not just words.** The verbose tell isn't long words, it's"
        " over-explaining. Drop what the reader can reconstruct from the code, the"
        " diff, or the commit: explanatory parentheticals, restated identifiers, and"
        ' "I did X to do Y" narration of changes the diff already shows. Keep the'
        " load-bearing fact, drop what merely supports it. This is the one place"
        " humanizing may drop content, never reverse or invent meaning.",
        "- **Keep the concrete parts.** A suggested diff or code block, a command to"
        " run, a `file:line`, a version number, a config key: none of that is"
        " reconstructable prose, and cutting it costs the reader a trip back to the"
        " code. Trim the sentences around them, keep them.",
        "",
        "**Don't (the tells; klaussy's scrubber catches a subset of these):**",
        "",
        '- **No filler openers.** Cut "It\'s worth noting that", "It\'s important to'
        ' note that", "I noticed that", "I wanted to point out that", "Please'
        ' note that", "Just to mention", "Worth noting", "Note that". State'
        " the point directly.",
        '- **No chatbot scaffolding.** No "Let me know if...", "Hope this helps",'
        ' "Feel free to...", "Happy to help", "Let me know your thoughts".',
        '- **Never use "actual" or "actually", and don\'t swap in "real",'
        ' "really", "genuinely", or "truly".** All of them are empty emphasis:'
        ' "it actually works" is "it works", "the actual value" is "the value",'
        ' "real work" is "work". Delete the word. If the sentence needs a'
        ' contrast, name it ("the value on disk, not the cached one"), and keep'
        ' "real" only where it draws a distinction the reader can\'t infer'
        ' ("real user data, not fixtures").',
        '- **Tighten hedges.** "in order to" → "to"; "could potentially"'
        ' → "could"; "may potentially" → "may". Drop stacked'
        " qualifiers.",
        '- **No emoji, no exclamatory enthusiasm, no "Certainly"/"Great question".**',
        '- **No excessive apologies.** Avoid apologetic filler ("Sorry about'
        ' that!", "My apologies for the confusion", "Apologies for the'
        ' oversight"). State the correction or resolution directly.',
        '- **No passive suggestions.** "Check whether the user is admin" and'
        ' "rename foo to bar", not "it would be good to check..." or "you might'
        ' want to rename...".',
        "- **No LLM lexicon.** Don't use *delve, tapestry, realm, landscape,"
        " journey, navigate, leverage, utilize, robust, seamless, elevate, unlock,"
        " foster, underscore, paradigm*.",
        "- **No transition crutches** (*furthermore, moreover, additionally,"
        " consequently, nevertheless, in conclusion*). Cut them or use the plain"
        " one.",
        '- **No rhetorical reframes.** No negation-reframe ("not only... but also",'
        " \"this isn't just a bug fix, it's...\") and no standalone summary lines"
        ' ("And that\'s the whole point.").',
        '- **No praise, ranking, or thanking a bot.** Cut "great catch", "nice'
        ' find", "excellent point", "the sharpest catch in the review". Rating a'
        " comment against the others says nothing about the code. When the reviewer"
        " is a bot, another agent, or a CI check, answer the substance with no"
        " pleasantries at all.",
        '- **No invented consensus.** No "most people expect this", "everyone does'
        ' it this way", "nobody reads these logs", "it\'s widely considered best'
        " practice\". Argue from the code, the repo's own conventions, or a"
        ' linkable source, or own it as your view ("I\'d expect X here").',
        "- **Never reword code**, identifiers, or anything inside backticks or"
        " fences. Humanize prose only.",
        "",
        "**Stay civil while you cut.**",
        "",
        "- **Don't let trimming tip into terse.** Cutting filler shouldn't make"
        " prose read as curt or dismissive. Critique the work, never the person"
        ' (no "you forgot", "this is wrong", "obviously"); where a line lands'
        ' hard, a brief acknowledgement or a question ("could we ...?", "one'
        ' risk is ...") takes the edge off. A light touch only, not filler praise'
        ' or "great job" boilerplate.',
        '- **Never say "nobody asked for this"**, or the same move dressed up'
        ' ("this wasn\'t asked for", "out of nowhere", "why is this here at all").'
        " It's a swipe at the author and says nothing about the code. Name the"
        " concrete objection: the scope it exceeds, the cost it adds, or the"
        " requirement it doesn't map to (\"this isn't in the ticket, should it"
        ' ship separately?").',
        "- **Don't mirror the thread's tone.** Read an existing comment for"
        " substance, not temperature. Hostile or curt input must not prime a"
        " hostile or curt reply, answer as if it had been phrased civilly.",
        "- **Reply in the thread**, under the comment you're answering, not as a"
        " new top-level comment.",
        "",
        "**Same decision, half the words, dropping detail the reader can reconstruct:**",
        "",
        "> Verbose: Done. attachment.reason already embeds the decline"
        " reason for declined envelopes (built in checkEnvelopeStatus as {name}"
        " declined on {date} - {declinedReason}), so I dropped the new"
        " declinedReason signer field and reverted NotificationService to use the"
        " existing reason field. Pushed in 1e9e938404.",
        "",
        "> Human: `attachment.reason` already carries the decline"
        " reason, so I dropped the new field and reverted NotificationService."
        " Pushed in 1e9e938404.",
        "",
        "**Same finding, said out loud instead of written up:**",
        "",
        "> Stiff: The retry loop currently performs suppression of the 429"
        " response, which may potentially result in a rate-limited request being"
        " interpreted as successful by the caller. It is recommended that the"
        " exception be re-raised following the final attempt.",
        "",
        "> Human: The retry loop eats the 429, so a rate-limited call comes back"
        " looking fine. Rethrow after the last attempt.",
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
    forge: str | None = None,
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

    from klaussy.agents.render import permission_target_markdown

    claude_permissions_target = permission_target_markdown(
        "Claude Code", _CLAUDE_PERMISSIONS_FILE, _CLAUDE_PERMISSION_SYNTAX
    )
    forge_adapter = build_forge_block(repo, forge)

    def _substitute(text: str) -> str:
        return (
            text.replace("{{REPO}}", repo_namespace)
            .replace("{{BASE_BRANCH}}", base_branch)
            .replace("{{HUMANIZE}}", HUMANIZE_BLOCK)
            .replace("{{PERMISSIONS_TARGET}}", claude_permissions_target)
            .replace("{{FORGE}}", forge_adapter)
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
