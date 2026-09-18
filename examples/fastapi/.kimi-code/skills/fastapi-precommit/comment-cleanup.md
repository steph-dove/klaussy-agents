# Concise-comment cleanup rules

These rules define how to tidy verbose comments that a change ADDED, so the commit lands with concise comments. They are the judgment half of the cleanup pass; the calling tool supplies the mechanical wrapper (which files to edit, the diff for context, and how to report what changed). This is a mechanical cleanup, not a review — never change behavior.

THE RULE: regular comments may be at most TWO sentences (aim for ONE); docstrings may be at most FIVE. Always as short as possible. Apply it like this:
- A regular comment longer than two sentences → tighten to one or two sentences keeping only the non-obvious WHY (intent, gotcha, invariant, link). Drop narration and restated mechanics.
- A comment that only restates what the code plainly does, narrates obvious steps, echoes a name, or is changelog/"AI-tell" filler ("// Now we handle…", "// This function will…", "// Added to fix the bug", "// increment i") → delete it entirely; it carries nothing worth one sentence.
- A docstring / JSDoc / public-API doc comment → condense to AT MOST five sentences and as short as possible: keep params, returns, and the why; cut narration and the obvious. Don't pad to five — shorter is better.
- A comment already within its limit and genuinely useful → leave it as is.

KEEP — never touch or shorten these:
- License or file-header comments
- Functional comments: shebang (#!), eslint-disable, @ts-ignore / @ts-expect-error, prettier-ignore, // @flow, # noqa, # type:, and similar pragmas; TODO/FIXME that carry real content

NOT A COMMENT — never touch these, no matter how long or prose-like they look:
- String and template literals: anything inside quotes or backticks. This includes multi-line PROMPT / instruction strings, SQL, HTML, regexes, and message text. A long prompt template is DATA the program uses at runtime, not a verbose comment — leave every character of it. The "//", "#", or "*" inside a string or a URL is not a comment marker.
- Commented-out code: a comment whose body is itself valid code. Leave it; it may be intentional. (You shorten prose comments, not code.)
- Anything that is actual code.

If you are not 100% certain a line is a natural-language source comment, leave it untouched.
