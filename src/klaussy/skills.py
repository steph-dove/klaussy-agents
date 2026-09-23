"""Scaffold .claude/skills/ with namespaced Claude Code skills."""

from __future__ import annotations

import re
from importlib import resources
from pathlib import Path

from rich.console import Console

from klaussy import __version__
from klaussy.forge import build_forge_tokens

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

# Not `templates/skills/`: `gh skill install` discovers any `skills/*/SKILL.md`
# in the tree and the spec has no opt-out. See tests/test_skill_discovery.py.
SKILL_TEMPLATE_ROOT = "templates/skill-templates"

# Marks a file as pre-substitution. Stripped to get the emitted filename.
TEMPLATE_SUFFIX = ".tmpl"


_TOKEN = re.compile(r"\{\{([A-Z_]+)\}\}")


def render_tokens(text: str, values: dict[str, str]) -> str:
    """Expand `{{NAME}}` tokens in a single pass; unknown names stay as written.

    Chained `str.replace` re-scans the text it just inserted, so a value that
    mentions a token got it expanded too: a CLAUDE.md documenting klaussy's
    placeholders pasted the whole humanize block into the review enrichment.
    """
    return _TOKEN.sub(lambda m: values.get(m.group(1), m.group(0)), text)


def template_output_name(filename: str) -> str:
    """The name a template is written out under, with the marker removed."""
    return filename.removesuffix(TEMPLATE_SUFFIX)


def iter_skill_templates(skill_dir):
    """Every template file in a skill's directory, in stable order.

    Anything without TEMPLATE_SUFFIX is skipped rather than emitted, so a stray
    `.DS_Store` or an editor backup never lands in a scaffolded repo.
    """
    return sorted(
        (f for f in skill_dir.iterdir() if f.name.endswith(TEMPLATE_SUFFIX)),
        key=lambda f: f.name,
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
    "worktree-cleanup",
    "restack",
    "split-pr",
    "adr-generator",
    "security-audit",
    "slop-coded",
    "rest-of-the-owl",
    "grant-permissions",
    "session-context",
]

VERSION_FILE = ".klaussy-version"

# Substituted into every skill that computes a diff range, via
# `{{BASE_RESOLUTION}}`. The base is chosen at scaffold time, which stops being
# true the moment a branch is cut from another topic branch, so the skills work
# it out against the repo instead and carry the answer as `<base>`.
BASE_RESOLUTION_BLOCK = (
    "**Resolve the base first.** Every range below is against `<base>`. Work it"
    " out once with `klaussy base --explain` and reuse that one value; if the"
    " `klaussy` CLI isn't on PATH, take `git symbolic-ref --short"
    " refs/remotes/origin/HEAD` without its `origin/` prefix, and `{{BASE_BRANCH}}`"
    " if that's empty too. If it names branches `HEAD` may have been cut from"
    " instead, this branch is probably stacked on one of them and the range would"
    " cover commits your change never added: ask which base to use, don't pick."
    " Say which base you used."
)

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
        "**Voice: say it out loud.** The target is a competent engineer typing"
        " this once, in a hurry, who isn't going to read it back. Not a careful"
        " writer, not a summary of the facts: a person with an opinion who wants"
        " to get on with their day.",
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
        "- **Type it once and don't polish it.** The last tell isn't a wrong"
        " word, it's evenness: every sentence complete, every paragraph the same"
        " shape, every point covered in order. Let it be uneven. A long sentence"
        " next to a three-word one. Two points where a tidy version would make"
        " four.",
        '- **Have a stance.** "I\'d drop this", "no idea why this is here",'
        ' "this\'ll fall over under load". First person and an opinion read as a'
        " person; an even, neutral summary reads as generated, however short it"
        " is.",
        "- **Skip the obvious.** A lazy writer leaves out what the reader can"
        " already see and doesn't round the thought off. \"Tests cover the happy"
        ' path and the concurrent case" is "tests for both". What it never drops'
        " is the thing being talked about: keep the nouns that carry the"
        ' meaning ("we invalidated the cache on every write", not "we invalidated'
        ' on every write"). Being lazy costs the reader nothing they needed.',
        "- **Don't mirror the source.** Same facts, your own shape: merge its"
        " paragraphs, reorder them, drop a section that isn't worth its space."
        " Keep every noun that carries meaning while you do it.",
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
        "**Answer what was asked, then stop.** Padding is the tell that survives"
        " every style fix, and it takes three shapes. All three are cuts, not"
        " rewrites:",
        "",
        "- **No closing principle.** Don't end by restating your decision as a"
        " general rule (\"I'd still reach for an iframe when you want a separate"
        ' document context for third-party code"). It answers nothing about this'
        " change and only validates the view you already gave. Stop at the last"
        " concrete point.",
        "- **No mechanism they didn't ask for.** Explaining how the thing works,"
        " in terms only you are holding in your head, reads as padding even to the"
        " person who wrote the code. If a paragraph doesn't change what the reader"
        " does next, cut it. When they need it, they'll ask.",
        "- **Grant a point in four words, or not at all.** Where the other person"
        " is right about something, say so and move on: \"Yes, Shadow DOM wouldn't"
        ' need the ResizeObserver" beats "the ResizeObserver cost is real and'
        " Shadow DOM wouldn't pay it\". Dressing agreement up in a metaphor is the"
        " most AI-sounding sentence in most replies. Never manufacture the"
        " agreement, though: if the author's answer is no, it stays no, and you"
        " don't go looking for something to validate on the way there.",
        "",
        "**Don't (mechanical tells).** klaussy's scrubber deletes these"
        " deterministically after you write, so don't spend attention on them:"
        " filler openers, chatbot scaffolding, apologies, praise or thanking a"
        " bot, *actual/actually*, *in order to*, *could/may potentially*,"
        ' *utilize/leverage*, *prior to*, emoji, and "Certainly"/"Great'
        " question\". Two the scrubber can't catch, so they're on you:"
        " **no LLM lexicon** (*delve, tapestry, realm, landscape, journey,"
        " navigate, robust, seamless, elevate, unlock, foster, underscore,"
        ' paradigm*) and **no rhetorical reframes** ("not only... but also",'
        ' "this isn\'t just a bug fix, it\'s...", or a smug standalone like "And'
        " that's the whole point.\").",
        '- **No invented consensus.** No "most people expect this", "everyone does'
        ' it this way", "nobody reads these logs", "it\'s widely considered best'
        " practice\". Argue from the code, the repo's own conventions, or a"
        ' linkable source, or own it as your view ("I\'d expect X here").',
        '- **No passive suggestions.** "Check whether the user is admin" and'
        ' "rename foo to bar", not "it would be good to check..." or "you might'
        ' want to rename...".',
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
        "",
        "**Tell-free but still generated, then written by a person.** Both say the"
        " same thing. The first is even: three paragraphs of the same shape, every"
        " sentence complete, no one behind it.",
        "",
        "> Tidy: The caching layer now uses a shared in-memory cache instead of a"
        " per-request database query, cutting the load on the primary instance."
        " The cache populates on first access and invalidates when the underlying"
        " record changes. This also fixes a subtle race condition where two"
        " simultaneous requests could both populate the same entry. Tests cover"
        " both the happy path and concurrent access.",
        "",
        "> Human: Swapped the per-request query for one shared cache, so the"
        " primary isn't getting hammered. Fills on first read, drops when the"
        " record changes. Also kills a race where two requests could populate the"
        " same key, there's a per-key lock now. Tests for both.",
    ]
)

# What `{{HUMANIZE}}` expands to everywhere but the humanize skill, which holds the
# rules. Kept out of HUMANIZE_BLOCK: `--rules` feeds tools with no skill to point at.
_HUMANIZE_SKILL_POINTER = (
    "**Humanize anything a human will read.** Before prose ships — a PR body, a"
    " review comment or reply, a commit message, a changelog entry, docs — run it"
    " through the `{{REPO}}-humanize` skill and use what comes back. That skill"
    " holds the rules; don't keep a second copy of them here.\n\n"
    "**The scrubber is not that pass.** `klaussy humanize` deletes a fixed"
    " list of mechanical tells (dashes, filler openers, a few hedges) and changes"
    " nothing else. It can't cut a paragraph that shouldn't exist, turn a noun"
    " phrase back into a verb, drop the closing principle, or make three sentences"
    " one, and that's most of what makes prose read as generated. Anything a human"
    " will read gets the `{{REPO}}-humanize` skill: cut, voice, check, then scrub."
    " Running the CLI, or `klaussy humanize --check`, is not that pass and doesn't"
    " stand in for it."
)


def humanize_pointer(repo_namespace: str) -> str:
    """Return the {{HUMANIZE}} expansion: a pointer to the repo's humanize skill.

    Only the humanize skill itself carries the rules (`{{HUMANIZE_RULES}}`); the
    other ten prose skills send the agent there instead of inlining them.
    """
    return _HUMANIZE_SKILL_POINTER.replace("{{REPO}}", repo_namespace)


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


ALIAS_PREFIX = "klaussy"

_DESCRIPTION_LINE = re.compile(r"^description: (.*)$", re.MULTILINE)


def apply_alias_to_frontmatter(text: str, skill: str, namespace: str) -> str:
    """Rewrite a rendered SKILL.md's description line to carry the alias."""
    head, sep, body = text.partition("\n---\n")
    if not sep:
        return text

    def _sub(match: "re.Match[str]") -> str:
        return f"description: {describe_with_alias(match.group(1), skill, namespace)}"

    return _DESCRIPTION_LINE.sub(_sub, head, count=1) + sep + body


def alias_name(skill: str) -> str:
    """The repo-independent name a user can call a skill by."""
    return f"{ALIAS_PREFIX}-{skill}"


def describe_with_alias(description: str, skill: str, namespace: str) -> str:
    """Append the stable alias to a skill description.

    Skills are namespaced per repo, so the same skill is `payments-review` in
    one checkout and `billing-review` in the next and nobody remembers which.
    Claude Code takes the slash command from the directory name and supports no
    alias field, so a second name has to reach the model some other way: naming
    it in the description is what lets "run klaussy-review" match. Skipped when
    the repo's own namespace already produces that name.
    """
    alias = alias_name(skill)
    if f"{namespace}-{skill}" == alias or alias in description:
        return description
    return f"{description} Also known as `{alias}`."


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


def skill_tokens(
    *,
    repo_namespace: str,
    base_branch: str = "main",
    forge: str | None = None,
    enrichment: str = "",
    permissions_target: str = "",
) -> dict[str, str]:
    """Every token a skill template can carry, with its value.

    One map, because there were three: scaffolding plus a copy in each eval
    harness. A token added to one and missed in another doesn't fail, it reaches
    the model as literal `{{...}}` text, which is how the e2e copy came to carry
    `{{FORGE}}` and `{{BASE_RESOLUTION}}`.
    """
    from klaussy.forge import forge_tokens

    return {
        "REPO": repo_namespace,
        "BASE_BRANCH": base_branch,
        "REPO_SPECIFIC_CHECKS": enrichment,
        "HUMANIZE": humanize_pointer(repo_namespace),
        "HUMANIZE_RULES": HUMANIZE_BLOCK,
        "BASE_RESOLUTION": render_tokens(BASE_RESOLUTION_BLOCK, {"BASE_BRANCH": base_branch}),
        "PERMISSIONS_TARGET": permissions_target,
        **forge_tokens(forge),
    }


def scaffold_skills(
    *,
    repo: Path,
    force: bool = False,
    review_template: Path | None = None,
    base_branch: str = "main",
    forge: str | None = None,
) -> list[Path]:
    """Create .claude/skills/<repo>-<skill>/SKILL.md for each shipped skill.

    `repo` is taken as given: the CLI and toolkit resolve it to the repository
    root first, and `--here` opts out of that.
    """
    repo = repo.resolve()
    skills_dir = repo / ".claude" / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)

    _migrate_legacy_commands(repo)

    existing_version = _read_version(skills_dir)
    if existing_version == __version__ and not force:
        console.print(f"[dim]Skills already up to date (v{__version__}), skipping.[/dim]")
        return []

    created: list[Path] = []
    templates = resources.files("klaussy").joinpath(SKILL_TEMPLATE_ROOT)

    repo_namespace = sanitize_skill_namespace(repo.name)

    from klaussy.agents.render import permission_target_markdown
    from klaussy.checklist import build_enrichment_block

    claude_permissions_target = permission_target_markdown(
        "Claude Code", _CLAUDE_PERMISSIONS_FILE, _CLAUDE_PERMISSION_SYNTAX
    )
    # Filled here rather than left for `klaussy checklist`, which only `init`
    # runs; `klaussy skills` and upgrades would otherwise ship the raw token.
    enrichment = build_enrichment_block(repo)

    tokens = {
        **skill_tokens(
            repo_namespace=repo_namespace,
            base_branch=base_branch,
            enrichment=enrichment,
            permissions_target=claude_permissions_target,
        ),
        # Detects the forge from the repo's remote, which the plain map can't.
        **build_forge_tokens(repo, forge),
    }

    def _substitute(text: str) -> str:
        return render_tokens(text, tokens)

    for skill in SKILL_NAMES:
        skill_dir = skills_dir / _skill_dir_name(repo, skill)
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_template_dir = templates.joinpath(skill)

        # Copy every template file in the skill dir. Skills like `review` ship
        # supporting files (e.g. sub-agents.md) alongside SKILL.md and need
        # them all written for the skill to function.
        for template_file in iter_skill_templates(skill_template_dir):
            filename = template_output_name(template_file.name)
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
            if filename == "SKILL.md":
                content = apply_alias_to_frontmatter(content, skill, repo_namespace)

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
