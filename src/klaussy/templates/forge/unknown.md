### Forge commands (provider not detected)

No hosting provider could be identified from `origin`. It may be a self-hosted install on a neutral hostname, a bare path, or the repo may have no remote at all.

Do the git-side work normally. For anything that lives on the hosting provider:

1. Ask the user which provider this is, or whether a CLI (`gh`, `glab`, ...) is installed and authenticated.
2. If one is present, confirm its interface with `<cli> --help` before the first call.
3. If not, ask the user to paste the ticket or request content, and hand back the exact steps for whatever has to change on their side.

Never invent a command, an endpoint, or a payload shape to fill the gap, and never ask the user to install a hosting CLI to finish work git can already do.
