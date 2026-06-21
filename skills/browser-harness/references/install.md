# browser-harness CLI — one-time install prerequisite

This is a **one-time prerequisite**, not part of the regular AI workflow. Do it once; after `browser-harness` prints page info, never repeat install/connection steps during normal browser work.

## Install the command

```bash
uv tool install browser-harness
command -v browser-harness   # should print a path
```

For browser-harness development, clone the repo into a durable path and run `uv tool install -e .` from the checkout.

## Register the skill

Install/register a skill named `browser-harness` with this trigger:

```text
Always use browser-harness for any web interaction: automation, scraping, testing, or site/app work.
```

Use this command for the skill body:

```bash
browser-harness skill
```

For Codex:

```bash
for root in "${CODEX_HOME:-$HOME/.codex}/skills" "$HOME/.agents/skills"; do
  rm -rf "$root/browser-harness" "$root/browser" "$root/browser-use"
done
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills/browser-harness"
browser-harness skill > "${CODEX_HOME:-$HOME/.codex}/skills/browser-harness/SKILL.md"
```

Only remove stale user-installed browser skills, never bundled/vendor plugin caches.

## Connect to a browser

`browser-harness` attaches to a Chrome you already have running, or to a Browser Use cloud browser. Quick check:

```bash
browser-harness <<'PY'
print(page_info())
PY
```

If that prints page info, you're done. If not, run `browser-harness --doctor` and follow the connection cases. The two connection methods:

- **Way 1 (real profile):** in your Chrome, open `chrome://inspect/#remote-debugging` and tick "Allow remote debugging for this browser instance" (sticky, per-profile). On Chrome 144+, click Allow on the first-attach popup. Inherits your logins/extensions — best when the agent acts in your everyday browser.
- **Way 2 (isolated profile, no popups):** launch Chrome with `--remote-debugging-port=9222 --user-data-dir=<non-default path>`, then set `BU_CDP_URL=http://127.0.0.1:9222`. Best for unattended automation.

The full connection reference and troubleshooting live in `docs/browser-connection.md`. Read it if the quick path above fails.

## Keeping current

`browser-harness` prints an update banner when a newer PyPI release exists; run `browser-harness --update -y` when you decide to upgrade. `browser-harness --doctor` also checks the latest version. Telemetry is anonymous and opt-out with `browser-harness telemetry disable`.

State lives under `${XDG_CONFIG_HOME:-~/.config}/browser-harness` by default: auth, selected profile, telemetry id, agent-workspace, runtime sockets, manager leases, logs, screenshots, and tmp files. Override with `BH_HOME` or `BROWSER_HARNESS_HOME`.
