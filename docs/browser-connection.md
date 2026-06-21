# Browser Connection Reference

Use this only when the quick path in `install.md` fails.

Browser-harness can connect to a local Chrome/Chromium browser or to a Browser Use cloud browser.

## Cloud Browsers

Start one with:

```python
b = browser_new("cloud")
browser(b["id"])
```

Authentication uses `BROWSER_USE_API_KEY` first, then the local `browser-harness auth login` store.

```bash
browser-harness auth login
browser-harness auth login --device-code
browser-harness auth login --api-key-stdin
browser-harness auth status
browser-harness auth logout
```

Never pass API keys as command-line arguments.

## Local Way 1: Real Profile

Use this when the agent should act in the user's everyday browser with real logins.

1. Ask the user to open Chrome.
2. Run:

   ```bash
   browser-harness <<'PY'
   print(browser_profiles())
   PY
   ```

3. Ask which stable `id` to use.
4. Save it:

   ```bash
   browser-harness <<'PY'
   browser_use_profile("PROFILE_ID_HERE")
   PY
   ```

5. In that Chrome profile, open `chrome://inspect/#remote-debugging`.
6. Tick "Allow remote debugging for this browser instance".
7. On Chrome 144+, click Allow when the per-attach popup appears.
8. Retry:

   ```bash
   browser-harness <<'PY'
   print(page_info())
   PY
   ```

On macOS, an agent can open the inspect page:

```bash
osascript -e 'tell application "Google Chrome" to activate' \
          -e 'tell application "Google Chrome" to open location "chrome://inspect/#remote-debugging"'
```

## Local Way 2: Isolated Profile

Use this for unattended automation or when permission popups are unacceptable.

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --remote-debugging-port=9222 \
  --user-data-dir="$HOME/.config/browser-harness/isolated-chrome" \
  about:blank
export BU_CDP_URL=http://127.0.0.1:9222
```

The `--user-data-dir` must not be Chrome's default profile directory. Chrome 136+ ignores `--remote-debugging-port` with the platform default profile path.

Copying a real Chrome profile into a custom directory is not a reliable login-preserving path because cookies are encrypted against the original profile context. Use Way 1 for real logins.

## Doctor Cases

Run:

```bash
browser-harness --doctor
```

Interpretation:

- `chrome running` FAIL: no compatible browser process was found. Ask the user to open Chrome or use Way 2/cloud.
- `daemon alive` FAIL with Chrome running: remote debugging permission is missing or the permission popup needs Allow.
- `active browser connections` is `0`: daemon is up but not attached to a usable page; retry after opening a normal tab.
- source mismatch: the command is importing a different install than the checkout you are reading.
- update available: run `browser-harness --update -y` if you want the new version.

Stale daemon reset:

```bash
browser-harness <<'PY'
restart_daemon()
PY
```

If that hangs, kill Chrome and browser-harness daemon processes, reopen Chrome, and retry. On macOS/Linux, remove lingering `bu-default.sock` and `bu-default.pid` files under `${XDG_CONFIG_HOME:-~/.config}/browser-harness/runtime`.

## Files

Default state directory:

```text
${XDG_CONFIG_HOME:-~/.config}/browser-harness
```

Important files:

```text
auth.json              Browser Use Cloud auth
settings.json          selected local Chrome profile and future preferences
telemetry.json         anonymous install id + telemetry opt-out
agent-workspace/       agent-written helpers and domain skills
runtime/               sockets, pids, manager leases, managed browser profiles
tmp/                   logs, screenshots, scratch files
```

Overrides:

```text
BH_HOME
BROWSER_HARNESS_HOME
BH_CONFIG_DIR
BH_AGENT_WORKSPACE
BH_RUNTIME_DIR
BH_TMP_DIR
```
