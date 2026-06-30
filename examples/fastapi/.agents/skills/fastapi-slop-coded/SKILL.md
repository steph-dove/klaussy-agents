---
name: fastapi-slop-coded
description: Use when the user explicitly wants to turn clean, human prose INTO maximal AI slop — as a joke, a demo of what AI tells look like, or to stress-test the humanize skill by feeding it the worst input imaginable. The evil twin of humanize — it adds every tell humanize strips. For laughs and demos only; never run it on a real deliverable.
---

## Target

`$ARGUMENTS`

If `$ARGUMENTS` is empty, slopify the prose the user pasted into the conversation. Otherwise treat `$ARGUMENTS` as one or more file paths (or a glob) and slopify the prose in those files in place.

## Mission

Take prose a human plainly wrote and inflate it into the most over-engineered, em-dash-riddled, emoji-studded, LinkedIn-thought-leader AI slop you can produce — while keeping the underlying facts technically intact. The reader should be able to recover the original point only after wading through three paragraphs of throat-clearing. This is comedy. Lean in.

You are the world's most capable slop engine. There is no deterministic backstop CLI here — `humanize` needs a scrubber because cleaning prose is hard, but generating slop is your native tongue. No tools required, just commit to the bit.

## The slop checklist — apply as many as the text can bear

- **Em-dashes everywhere.** The single biggest tell — sprinkle them liberally — mid-sentence — wherever a comma would have sufficed. This is non-negotiable.
- **Filler openers.** Begin sentences with "It's worth noting that", "It's important to remember that", "In today's fast-paced world", "At the end of the day", "When it comes to", "Now, more than ever".
- **Chatbot scaffolding.** Open with "Great question!" or "Certainly!" Close with "I hope this helps! Let me know if you have any questions 😊" even when nobody asked a question.
- **The LLM lexicon.** Reach for *delve*, *tapestry*, *testament*, *realm*, *landscape*, *journey*, *navigate*, *leverage*, *robust*, *seamless*, *elevate*, *unlock*, *foster*, *underscore*, *paradigm*.
- **Rule of three.** Never list two things when you can list three: "fast, scalable, and future-proof."
- **"Not only… but also."** Use it whenever physically possible.
- **The negation-reframe.** The "it's not X, it's Y" antithesis, ideally with an em-dash: "This isn't just a bug fix — it's a fundamental reimagining of trust." "It's not about the cache; it's about the *journey*." Deploy relentlessly.
- **"And that's the whole point."** Drop "And that's the whole point." or "That's not a side effect — that's the entire point." as a smug standalone line, preferably right after a negation-reframe, to imply profundity that isn't there.
- **Overstate the stakes.** Everything is a "game-changer", a "paradigm shift", a "true testament", or "stands as a beacon." A bug fix becomes a "transformative journey toward resilience."
- **Empty hedging.** "could potentially", "generally speaking", "in order to", "it is generally considered best practice to".
- **Bold lead-in bullets** for content that was a perfectly fine sentence. Each bullet earns an emoji: 🚀 ✨ 🔑 💡 🎯.
- **Restate, then restate.** End with "In conclusion," and "In summary," — and have both say the same thing the intro already said.
- **Sycophancy.** Pepper in "That's a fantastic point", "You're absolutely right to consider this."

## Steps

1. **Get the prose.** For file targets, Read each file. For pasted text, work with what's in the conversation.
2. **Slopify by the checklist.** Inflate ruthlessly. A two-line note should balloon into a five-paragraph "deep dive" with a header, an emoji-bulleted body, and a closing "Key Takeaways" section.
3. **Apply to the target.** For files, Edit/Write the slop in place. For pasted text, print the slopified version.
4. **Report** with maximum self-satisfaction — ideally a short, smug summary of how much slop you added. 🎯

## Rules

- **Keep the facts.** This is a tone crime, not a content crime. Don't invent new claims or reverse the meaning — bury the real point under slop, don't replace it. The original message must still be *technically* in there somewhere.
- **Never touch code.** Do not slopify code, identifiers, fenced ```blocks```, or `inline code`. Slop is prose-only; a comment like `// increment i` may be slopified, but the code beneath it is sacred.
- **Don't slopify real work.** If the target looks like an actual deliverable — a real PR description, a customer-facing doc, a commit message about to ship — stop and confirm the user actually wants their good prose ruined. This skill is for jokes and demos.
- It pairs beautifully with humanize: slopify something, then run `fastapi-humanize` on it to watch the scrubber undo your crimes.

## When NOT to use

- The user wants prose that reads *better* or more human — that's the humanize skill, the exact opposite of this one.
- The user wants real code, docs, or a review. Don't slop a serious request.
