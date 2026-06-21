---
name: browser-install
description: Install browser-harness into the current agent and connect it to a browser with minimal prompting.
---

# `browser-harness` installation

Use this file only for browser-harness install, browser connection setup, and connection troubleshooting. For day-to-day browser work, read `SKILL.md`. Task-specific edits belong in `agent-workspace/agent_helpers.py` and `agent-workspace/domain-skills/`.

## Recommended `browser-harness` setup

Install the released package as a global uv tool:

```bash
uv tool install browser-harness
command -v browser-harness
```

For browser-harness development, clone the repo into a durable path and use `uv tool install -e .` from the checkout. Normal users and other agents should use the PyPI package.

## Make browser-harness global for the current agent

After the command is installed, register a skill named `browser-harness` with this trigger:

```text
Always use browser-harness for any web interaction: automation, scraping, testing, or site/app work.
```

Use `browser-harness skill` to print the packaged skill text.

Before registering it, remove stale user-installed browser skills that came from old browser-harness installs. Do not edit bundled/vendor plugin caches.

- **Codex**: add the printed skill as a global skill at `$CODEX_HOME/skills/browser-harness/SKILL.md` (often `~/.codex/skills/browser-harness/SKILL.md`).

  ```bash
  for root in "${CODEX_HOME:-$HOME/.codex}/skills" "$HOME/.agents/skills"; do
    rm -rf "$root/browser-harness" "$root/browser" "$root/browser-use"
  done
  mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills/browser-harness"
  browser-harness skill > "${CODEX_HOME:-$HOME/.codex}/skills/browser-harness/SKILL.md"
  ```

- **Claude Code**: paste or import the output of `browser-harness skill` into the global instruction file Claude Code uses for reusable skills.

- **Other agents**: tell the agent to install/register a skill named `browser-harness`, use the trigger above verbatim, and use `browser-harness skill` as the skill body.

This makes new agent sessions in other folders load the runtime browser harness instructions automatically.

## Keeping the harness current

- On each run, `browser-harness` prints `[browser-harness] update available: X -> Y` (once per day) when a newer PyPI release exists.
- `browser-harness --doctor` also checks the latest PyPI version.
- When you see an update banner, decide whether to run `browser-harness --update -y`. It pulls the new code (`git pull --ff-only` for editable clones, `uv tool upgrade browser-harness` for PyPI installs) and stops the running daemon so the next call picks up the new code. With `-y` it won't prompt.
- `--update` refuses to run on an editable clone with uncommitted changes. If that happens, tell the user and let them resolve the dirty worktree.
- PyPI installs require `uv` for updates; there is no pip fallback.

## Maintenance commands

- browser-harness --doctor — show version, install mode, daemon and Chrome state, and whether an update is pending.
- browser-harness telemetry status — show opt-out telemetry state.
- browser-harness telemetry disable — opt out of anonymous usage telemetry.

## Files on disk

By default browser-harness keeps its state under `${XDG_CONFIG_HOME:-~/.config}/browser-harness`:

```text
auth.json              Browser Use Cloud auth
settings.json          selected local Chrome profile and future preferences
telemetry.json         anonymous install id + telemetry opt-out
agent-workspace/       agent-written helpers and domain skills
runtime/               sockets, pids, manager leases, managed browser profiles
tmp/                   logs, screenshots, scratch files
```

Override the whole home with `BH_HOME` or `BROWSER_HARNESS_HOME`. Override specific dirs with `BH_CONFIG_DIR`, `BH_AGENT_WORKSPACE`, `BH_RUNTIME_DIR`, or `BH_TMP_DIR`.

## Architecture

```text
Chrome / Browser Use cloud -> CDP WS -> browser_harness.daemon -> IPC -> browser_harness.run
                                      ^
optional browser_harness.manager_daemon owns many isolated browser leases
```

- The CLI talks to a local per-browser daemon over IPC.
- `BU_CDP_URL` points the normal local-browser daemon at a specific DevTools HTTP endpoint for Way 2.
- The browser manager auto-starts when `browser`, `browser_status`, `browser_new`, `browser_list`, or `browser_close` is used.
- Managed browser scripts select an explicit short id with `browser(id)`; agents should not set daemon namespace variables for normal use.
- Cloud browser creation reads Browser Use auth from `BROWSER_USE_API_KEY` first, then the local `browser-harness auth login` store.

## Browser Use Cloud auth

For cloud browsers, prefer OAuth login over pasting API keys:

```bash
browser-harness auth login
```

The command generates a PKCE login request, opens or prints a Browser Use login URL, waits for the local callback, exchanges the code for an API key, and stores it in a private local file. The key is never printed.

Headless/SSH fallback:

```bash
browser-harness auth login --device-code
```

If you already have a Browser Use API key, store it safely through stdin:

```bash
browser-harness auth login --api-key-stdin
```

Do not pass API keys as command-line arguments; they can leak through shell history and process listings.

Other auth commands:

```bash
browser-harness auth status
browser-harness auth logout
```

Key resolution order for cloud browser creation:

```text
BROWSER_USE_API_KEY
  -> stored browser-harness auth key
  -> cloud-auth-required
```

# Browser connection setup and troubleshooting

## Browser connection reference

This section is the source of truth for how browser-harness connects to a browser. It is the canonical reference for every agent and user of this repo. Every statement here is intended to be verifiable against either an official Chrome source or this repo's own code, and is held to that standard deliberately. If anything below is incorrect, incomplete, or misleading, open an issue on the browser-harness repository immediately with clear evidence and explanation so it can be corrected. Do not silently work around an error in this document; the cost of one user being misled is much higher than the cost of one issue.

Browser-harness can connect to any Chrome or Chromium-based browser on your computer, or to a Browser Use cloud browser.

**Cloud browsers** are managed by the Browser Use cloud API. Start one with `browser_new("cloud", proxy_country="us")`, keep the returned `id`, and call `browser(id)` before page helpers in each script. Authentication is via `BROWSER_USE_API_KEY` or `browser-harness auth login`; the harness handles the WebSocket URL itself. Cookie profile sync is advanced and opt-in; read `interaction-skills/profile-sync.md` only when the user explicitly asks to sync local cookies into Browser Use cloud profiles.

**Local browsers** require remote debugging to be enabled. There are two ways, and they suit different use cases.

Local Way 1 also requires an explicit selected profile before the harness attaches. Run `browser_profiles()` to get stable ids such as `google-chrome:Default`, then `browser_use_profile("google-chrome:Default")`. The daemon snapshots that selected profile at startup and refuses to attach to an arbitrary available Chrome profile.

*Way 1: chrome://inspect/#remote-debugging checkbox — uses your real profile.* In your running Chrome, navigate to `chrome://inspect/#remote-debugging` and tick the "Allow remote debugging for this browser instance" checkbox. This setting is per-profile and sticky: tick it once and it persists across every future Chrome launch of that profile. Then run any `browser-harness` command. On Chrome 144 and later, the first attach by the harness triggers an in-browser "Allow remote debugging?" popup that you must click Allow on. The popup may reappear on later attaches under conditions that are not fully characterized.[^1] This path inherits your everyday Chrome's logins, extensions, history, and bookmarks, which makes it the right choice for an agent helping you with tasks in your real browser.

*Way 2: command-line flag — uses an isolated profile, no popups ever.* Launch Chrome with `--remote-debugging-port=9222 --user-data-dir=<path>`. Two precisions:

- The path must be a directory that is **not** Chrome's platform default (`%LOCALAPPDATA%\Google\Chrome\User Data` on Windows, `~/Library/Application Support/Google/Chrome` on macOS, `~/.config/google-chrome` on Linux). On Chrome 136 and later, the port flag is silently no-opped when the user-data-dir is the platform default, even if you pass it explicitly. An empty or new path gives a fresh clean profile that Chrome will persist there across future runs.
- This path does **not** let you reuse your everyday Chrome profile. Copying the default profile's files into a custom directory makes Chrome accept the flag, but cookies are encrypted under a key bound to the original directory and will not survive the copy — so you carry over bookmarks and extensions but lose every logged-in session. If you want your real logins, use Way 1.

Tell the harness which port you launched on by setting `BU_CDP_URL=http://127.0.0.1:9222` before running `browser-harness`.

For most tasks where the agent acts on your behalf in your normal browser, use Way 1. For automation that runs without you watching, or any case where popup interruptions are unacceptable, use Way 2 or a cloud browser.

[^1]: The conditions that cause Chrome to re-show the "Allow remote debugging?" popup on a subsequent attach (time elapsed since previous Allow, daemon restart, browser restart, new CDP session, version-dependent options like "Allow for N hours") are not fully characterized. Way 2 sidesteps this entirely.

## First time setup

Try yourself before asking the user to do anything. Retry transient errors briefly. Only ask the user when a step genuinely needs them — ticking a checkbox, clicking Allow.

If the user hasn't said which connection method to use, default to Way 1 if Chrome is already running, Way 2 if not. Cloud is only used when the user opts in.

1. Try the harness:

   ```bash
   browser-harness <<'PY'
   print(page_info())
   PY
   ```

   If it prints page info, you're done. If it reports `needs-profile`, run `browser_profiles()`, choose a stable profile id with the user, call `browser_use_profile(profile_id)`, then retry. For private or cloud manager browsers, use `browser_new(...)` first, then select the returned id with `browser(id)`.

2. Otherwise run `browser-harness --doctor`. The two lines that matter for connection are `chrome running` and `daemon alive`.

3. Match the output to a case:

   - **chrome FAIL** → no Chrome process detected.
     - **Way 1**: ask the user to open their target Chrome themselves.
     - **Way 2**: launch Chrome yourself with `--remote-debugging-port=9222 --user-data-dir=<non-default path>`, then set `BU_CDP_URL=http://127.0.0.1:9222` for the harness (see the Browser connection reference).

   - **chrome ok, daemon FAIL** → Way 1 setup is incomplete. Tell the user to:
     - navigate to `chrome://inspect/#remote-debugging` in their Chrome and tick "Allow remote debugging for this browser instance" if not yet ticked (one-time per profile)
     - click Allow on the in-browser popup if it appears (every attach on Chrome 144+)

     On macOS, you can open the inspect page in their running Chrome yourself instead of asking them to navigate:

     ```bash
     osascript -e 'tell application "Google Chrome" to activate' \
               -e 'tell application "Google Chrome" to open location "chrome://inspect/#remote-debugging"'
     ```

   - **chrome ok, daemon ok, but step 1 still failed** → stale daemon. Restart it:

     ```bash
     browser-harness <<'PY'
     restart_daemon()
     PY
     ```

     If that hangs, escalate: kill all Chrome and daemon processes, then reopen Chrome and retry. On macOS/Linux, also remove lingering `bu-default.sock` and `bu-default.pid` files under `${XDG_CONFIG_HOME:-~/.config}/browser-harness/runtime`.

4. After any fix, retry step 1.

If Way 1 fails repeatedly or the user's task is unattended, move to Way 2 or a cloud browser per the Browser connection reference (these have no popups).

If you are testing browser connection for the first time, run this demo: open `https://github.com/browser-use/browser-harness` in a new tab and activate it (`switch_tab`) so the user sees the harness has attached. Then ask what they want to do next.
