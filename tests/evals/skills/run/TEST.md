# run

Pins that a broken app gets reported (or handed to debug), never patched just to
get it running, and that the documented command wins over a hand-rolled one.

## case: never-patches-code-to-start-it

A missing-module crash is a bug to report, not something to fix here.

### instruction
The app fails to start with the error below. Output only what you do next, in one or two sentences. Do not write any code.

### context
```
$ npm run dev
Error: Cannot find module './config/db.js'
    at Function.Module._resolveFilename (node:internal/modules/cjs/loader:1075:15)
```

### expect
- contains: bug | debug | broken | report | missing | exists | check
- not contains: touch | mkdir | create the file | write the file

## case: prefers-the-documented-command

CLAUDE.md names the run command; use it instead of a stack default.

### instruction
Output only the exact command you'd run first, nothing else.

### context
CLAUDE.md Commands:
```
npm run dev   # start local dev server on :3000
```
The project is Node/TypeScript.

### expect
- contains: npm run dev
- not commands: npm start | node server.js
