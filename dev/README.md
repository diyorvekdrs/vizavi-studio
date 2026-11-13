# For the maintainer

Everything in `dev/` is for working on Vizavi Studio – it is **not** part of the download your friends get
(`.gitattributes` keeps it out of the release zip, and the app never installs it).

## Publish a new version

1. Change the code in `app\` (and add tests in `tests\`).
2. Run the tests: `py -3 tests\run_all.py` (once: `npm install` in `tests\` for the UI test).
3. Double-click **`dev\Publish update.cmd`** and type one line about what's new, plus patch / minor / major.

The script (`dev/publish_update.py`) raises the version in `app/studio/version.py`, writes `app/release.json`,
commits, tags `vX.Y.Z`, pushes, builds the release zip with its SHA-256 and publishes the GitHub release
(also as `Vizavi-Studio-Setup.zip` and `Vizavi-Studio-Installer.cmd`). Installed apps offer the update within a few
hours, or right away with **Settings → Check now**.

- Needs [git](https://git-scm.com) and the [GitHub CLI](https://cli.github.com) (`gh auth login`).
- Dry run – lists what would be published, changes nothing: `py -3 dev\publish_update.py --dry`.
- Only what `.gitignore` allows is ever published (it is a whitelist): settings, projects, models, the Python
  environment, logs and your own library stay on your PC. The script stops if a private file would be committed.

## Tests

`tests/run_all.py` runs every suite: `t_api`, `t_core`, `t_checks`, `t_mcp`, `t_media_styles`, `t_models`, `t_render`,
`t_trash`, `t_update` and the jsdom UI test `ui_test.js`. GitHub runs them on Windows for every push
(**Actions → Tests**, `.github/workflows/tests.yml`). Publish only when they are green. Tests never touch the real
`settings.json` (they point `VZ_SETTINGS` / `core.SETTINGS` at a temp file).

## Where things are

| Path | What |
|---|---|
| `app/Vizavi Studio.pyw` | starts the local engine and opens the window |
| `app/studio/` | the engine: `server.py` (HTTP API + job worker), `core.py` (projects, packages, renders, checks), `order.py`, `transcribe.py`, `media.py`, `update.py`, `trash.py`, `mcp_server.py` (chat mode), `claude_link.py` |
| `app/ui/` | the window (vanilla HTML/CSS/JS) |
| `app/kit/` | render kit copied next to Claude's code: `vzrender.py`, `vzfast.py`, GPU backend |
| `app/claude/` | what goes into the packages for Claude: rules, direction, engine docs, task texts, templates, tools, fonts |
| `app/setup/` | `install.ps1`, `uninstall.ps1` |
| `docs/` | README pictures (not in the download) |
| `get.ps1`, `Vizavi-Studio-Installer.cmd`, `Install Vizavi Studio.cmd` | the three ways to install (keep `get.ps1` at the root – installed copies of the quick installer download it from there) |

More about features and folders: [`app/README.md`](../app/README.md).
