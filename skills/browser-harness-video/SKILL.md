---
name: browser-harness-video
description: Turn browser-harness session recordings into trustworthy, privacy-safe explanatory videos. Use when a user asks or nudges the agent to show, record, demo, explain, or make a video of browser work, or when an agent needs to edit, retime, narrate, review, redact, or export an explicitly requested recording folder containing events.jsonl and numbered JPEG frames. Do not trigger merely because a browser task was significant.
---

# Browser Harness Video

Build a comprehension-first video from a browser-harness recording. Put only
editorial choices in `edit-brief.json`. The compiler owns the complete v9 house
style and writes `composition.js`; never author or patch that file by hand.

Require user intent. Natural phrases such as “show me what you did,” “record
this,” “make a video,” “demo it,” or “walk me through it” are sufficient; an
exact keyword is not. A significant browser task without such a nudge does not
justify video production.

## Workflow

1. From the browser-harness repository root, discover the canonical recording
   path. Do not guess from environment variables or use a depth-limited search:

   ```bash
   REC="$(./browser-harness recordings --latest)"
   ```

   Outside a development checkout, use `browser-harness` without `./`.
2. From the browser-harness repository root, prepare it:

   ```bash
   uv run skills/browser-harness-video/scripts/init_video.py <recording-dir>
   ```

3. Read `<recording-dir>/recording-summary.json`, the relevant frames, and
   `references/edit-brief.md`.
4. Write `<recording-dir>/edit-brief.json`, then compile it:

   ```bash
   uv run skills/browser-harness-video/scripts/compose_video.py <recording-dir>
   ```

   If the compiler rejects a field or duration, simplify the brief. Do not
   patch its output or add a timing exception.
5. Build one causal story: task and plan, meaningful actions, wrong-turn
   explanation when needed, correction, verification, explicit outcome.
6. Add opaque page-coordinate redactions and list every used frame in
   `privacy.reviewedFrames` only after inspecting it at full resolution.
7. Run the blocking preflight:

   ```bash
   uv run skills/browser-harness-video/scripts/audit_video.py <recording-dir>
   ```

   Read the generated contact sheet and every image in `.privacy-review/` at
   full resolution. Fix every error and inspect every unmasked field before
   continuing. Never share these local review artifacts.
8. Generate deterministic renderer review sheets:

   ```bash
   uv run skills/browser-harness-video/scripts/render_video.py review <recording-dir>
   ```

   The command serves the editor locally, disables recording the editor itself,
   runs both renderer preflights, captures every beat in normal and reduced
   motion, and captures the exact click and result states. Inspect
   `renderer-normal-contact-sheet.jpg`, `renderer-reduced-contact-sheet.jpg`,
   and `renderer-click-contact-sheet.jpg` when present.
9. After actually inspecting every sheet, export and verify the MP4:

   ```bash
   uv run skills/browser-harness-video/scripts/render_video.py export <recording-dir> --reviewed
   ```

   `--reviewed` is an attestation, not a shortcut. The command refuses stale or
   failed audits, exports in real time, converts to H.264, decodes the complete
   file, checks its duration, and writes `renderer-final-contact-sheet.jpg`.
   Inspect that final sheet before sharing `video.mp4`.

## Story contract

- Optimize the main cut for a first-time viewer. The raw trace remains the
  forensic artifact.
- Keep narration to one idea and at most seven words. Let it persist across
  multiple visual beats.
- Put detailed reasoning on still explanation cards, not moving subtitles.
- Optimize for a quick first viewing; viewers who want every detail can pause.
- Pace structured cards at 380 WPM and moving captions at about 0.2 seconds per
  word. The compiler blocks a normal cut above 22 seconds and grants extra time
  only for more than five meaningful actions or more than one explanation.
- Set narration only when the thought changes. Let one thought span two or
  three raw frames instead of restating it on every action.
- Use exactly `Observed`, `Mistake`, `Correction` for wrong-turn explanation
  points. Author them in that causal order; they reveal sequentially.
- Use a 2–5 step plan and set `chapter` on normal beats.
- Show a click consequence in the same beat with `after` whenever possible.
- Before an explanation or outcome card replaces raw browser evidence, preserve
  the visible end state for the compiler-owned raw-to-card hold. Do not cut
  directly from click feedback into a full-screen text card.
- End with an `outcome` card that restates what was actually achieved.
- Preserve an informative wrong turn, but remove waits, retries, and motion
  that do not change the viewer's mental model.

## Motion contract

- Keep click-to-result feedback below 80ms. Pair `event` with `afterEvent`; the
  compiler and renderer own the actual reaction timing.
- Maintain one close zoom band across adjacent actions and pan gently.
- Set `context: true` only for a deliberate orientation shot. The compiler
  chooses wide shots and camera cuts; never author zoom or pan coordinates.
- Keep the cursor screen-sized: larger in wide shots, quieter in close shots.
- Keep clicks inside the safe viewport. The renderer pulls back near page
  edges so captions, telemetry, and the video boundary cannot hide the click.
- Respect reduced motion; it must snap without camera travel or shakes.
- Prefer `frameStyle: "native"`: a minimal title strip preserves the raw frame
  without inventing a URL. Use synthetic browser chrome only when it is truly
  captured or explicitly requested.

## Authenticity contract

- Treat captured frames, cursor motion, clicks, and typing as evidence. Preserve
  them unless privacy requires an opaque mask.
- Use only frames captured while completing the original task. Never reenact
  the task or create a page, dashboard, or result solely to improve the video.
- Keep subtitles and chapter progress outside the captured app surface. Do not
  add explanatory labels on top of raw frames.
- Use the native system font and `frameStyle: "native"` by default. Do not
  invent a URL, tab title, browser state, timestamp, user value, or success.
- Let subtitles persist while raw frames advance when one thought spans several
  actions. Do not force text and screenshots to change at the same cadence.

## Privacy contract

- On private account/admin surfaces, treat emails, customer or tenant domains,
  tenant/object IDs, passwords, tokens, identity chips, unrelated people, and
  raw SPA routes as sensitive by default.
- Public source content is evidence. Do not redact public authors, post text,
  or link domains merely because they are usernames or domains.
- Use `route` for a short semantic location. Never display a raw trace URL.
- Use opaque masks. Blur and pixelation are not sufficient for secrets.
- Prefer quiet, surface-matched masks over high-contrast censorship blocks.
  Mask colors must be opaque six-digit hex values; use per-rectangle style
  overrides when a header and content area need different treatments.
- Keep redaction active on both `frame` and `after` states.
- Do not add a frame to `privacy.reviewedFrames` until a human or agent has
  inspected the final masked frame at maximum zoom.
- The renderer refuses export when any used frame lacks review coverage.

## Reusable files

- `interaction-skills/video-template.html` — shared deterministic renderer
- `interaction-skills/make-video.md` — composition schema and editing guidance
- `references/edit-brief.md` — the deliberately small editorial schema
- `scripts/init_video.py` — copy the renderer and summarize a trace safely
- `scripts/compose_video.py` — compile the brief into the locked v9 house style
- `scripts/audit_video.py` — validate story/privacy and build a local contact sheet
- `scripts/render_video.py` — automate renderer review, export, and MP4 verification

Do not fork the template into a recording or patch generated composition. Make
general improvements in the shared renderer/compiler, and keep task-specific
decisions in `edit-brief.json`.

## Delegated post-production

When a primary agent delegates this work, treat the recording directory and
original task as immutable inputs. Do not operate the live task page. Set
`BH_RECORD=0` for editor/browser review so the video session does not record
itself. Return the verified MP4 path and a concise audit result to the primary
agent.
