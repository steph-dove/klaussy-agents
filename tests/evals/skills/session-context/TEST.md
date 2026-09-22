# session-context

Pins that notes are written to the exact `$KLAUSSY_SESSION_NOTES_DIR` path — never guessed, never into the repo — and that session notes are skipped entirely when the variable isn't set.

## case: writes-to-the-exact-env-path

The notes directory is used exactly as given, never rebuilt or substituted with a path inside the repo's working tree.

### instruction
You just discovered the API's local port moved from 8000 to 8010, which another agent in this session would otherwise hit blindly. Output only the file path you would write the note to.

### context
`$KLAUSSY_SESSION_NOTES_DIR` is `/private/tmp/klaussy-session-7f3a`.

### expect
- contains: /private/tmp/klaussy-session-7f3a
- not contains: .claude/ | git add | committed

## case: skips-entirely-when-unset

An unset notes directory means the agent isn't in a klaussy session, so session notes are skipped rather than written somewhere improvised.

### instruction
The user asks you to write a session note about a breaking schema change. What do you do? Answer in one sentence.

### context
`$KLAUSSY_SESSION_NOTES_DIR` is not set in this session.

### expect
- contains: not set | unset | not running in a klaussy session | skip
- not contains: /tmp/
