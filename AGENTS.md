browser-harness is a thin layer that connects agents to browsers via an editable CDP harness.

# Code priorities
- Clarity
- Precision
- Low verbosity
- Versatility

# Overview
Core code lives in `src/browser_harness/`:
- `admin.py` — daemon lifecycle, diagnostics, updates, profile management
- `daemon.py` — the long-lived middleman process between the browser and the agent
- `helpers.py` — CDP wrapper and core browser primitives auto-imported into `-c` scripts
- `run.py` — the `browser-harness` CLI

`SKILL.md` tells agents how to use the harness and CLI.
`install.md` tells agents how to install it, attach a browser, and troubleshoot.
In this checkout, invoke the current source with `./browser-harness`; do not use
a globally installed `browser-harness` binary.

For any session-recording or video task, read
`skills/browser-harness-video/SKILL.md` fully and reuse the shared renderer.
Do not invent a separate editing workflow.

Recording and video creation require user intent. Treat any natural-language
nudge such as “show me what you did,” “record this,” “make a video,” “demo it,”
or “walk me through it” as opt-in; do not require exact wording. Significant
work alone is not consent. Discover existing evidence with
`./browser-harness recordings --latest`; never reenact a task. When a video was
requested and subagents are available, delegate only video post-production so the
primary agent can keep validating and handing off the requested result.

An agent operating the harness only edits inside `agent-workspace/`:
- `agent_helpers.py` — task-specific browser helpers the agent adds
- `domain-skills/` — skills the agent writes and reads

# Contributing
Consider what is really needed. Prefer the smallest diff that fixes the bug.
