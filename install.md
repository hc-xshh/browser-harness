---
name: browser-install
description: Install browser-harness and connect it to a browser fast.
---

# browser-harness install

Use once. For browser work, read `SKILL.md`.

## Fast Path

```bash
uv tool install browser-harness
for root in "${CODEX_HOME:-$HOME/.codex}/skills" "$HOME/.agents/skills"; do
  rm -rf "$root/browser-harness" "$root/browser" "$root/browser-use"
done
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills/browser-harness"
browser-harness skill > "${CODEX_HOME:-$HOME/.codex}/skills/browser-harness/SKILL.md"
browser-harness <<'PY'
print(page_info())
PY
```

If `page_info()` prints, stop. Setup is done.

For Claude Code or other agents: install `browser-harness`, register a skill named `browser-harness`, use `browser-harness skill` as the body, and use this trigger verbatim:

```text
Always use browser-harness for any web interaction: automation, scraping, testing, or site/app work.
```

Only remove stale user-installed browser skills. Do not edit bundled/vendor plugin caches.

## If It Says `needs-profile`

```bash
browser-harness <<'PY'
print(browser_profiles())
PY
```

Ask the user which stable `id` to use, then retry:

```bash
browser-harness <<'PY'
browser_use_profile("PROFILE_ID_HERE")
print(page_info())
PY
```

## If Chrome Blocks It

In the selected Chrome profile:

1. Open `chrome://inspect/#remote-debugging`.
2. Tick "Allow remote debugging for this browser instance".
3. Click Allow on the popup if it appears.
4. Retry `page_info()`.

## If Still Broken

```bash
browser-harness --doctor
```

Use the output:

- `chrome running` FAIL: ask the user to open Chrome, or use isolated/cloud browser.
- `daemon alive` FAIL: Chrome remote debugging permission is missing.
- update available: run `browser-harness --update -y` if you want it.

For full details, read `docs/browser-connection.md`.

Useful:

```bash
browser-harness --update -y
browser-harness telemetry disable
```
