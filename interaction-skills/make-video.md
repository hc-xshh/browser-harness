# Making a video from a recording

Turn a browser-harness session into a clear, privacy-safe explanatory video.
The numbered JPEGs and `events.jsonl` are source evidence; `edit-brief.json`
is the editorial story; the compiler and `video-template.html` are the shared
house style.

Create a video only when the user asks or naturally nudges toward seeing the
work. Significant browser work alone is not consent.

For the complete reusable workflow and blocking audit, read
`skills/browser-harness-video/SKILL.md`.

Discover the recording with `browser-harness recordings --latest` (or
`./browser-harness recordings --latest` in a development checkout). Never
guess the workspace path, infer recording state from an unset environment
variable, reenact the task, or build a synthetic page solely for the video.

## Story

- Start with the task plus a 2–5 step plan and leave it up long enough for a
  quick, structured scan.
- Use the pause-friendly 380 WPM scan target. A normal cut has a hard 22-second
  budget; the compiler grants extra time only for genuinely larger stories.
- Build one causal chain: intent → action → visible result.
- Keep narration to one thought and usually 3–7 words. Set it only when the
  thought changes and let it persist across two or three screenshots.
- Put detailed reasoning on a still `explanation` card. A useful wrong turn
  should say what was observed, why it happened, and what changes next.
- Use exactly `Observed`, `Mistake`, `Correction` for a wrong turn. Author them
  in that causal order; the renderer reveals them sequentially.
- Remove waits, retries, and motion that do not change the viewer's model.
- End with an `outcome` card listing what was actually achieved and verified.

The main cut is for first-time comprehension. The raw trace remains the
forensic artifact for debugging.

## Motion

- Cursor and typing beats auto-frame. Consecutive close actions stay in one
  zoom band and pan gently between targets.
- Use `wide: true` for deliberate context shots, not between every action.
- Use `cameraCut: true` when a distant target would require a painful pan.
- Pair a click with `after`; the result appears within about 65ms. Add
  `afterRoute` when the semantic location changes with it.
- The cursor remains screen-sized and grows in wide shots.
- Keep every click inside the renderer's safe area. Edge clicks automatically
  pull the camera back so captions and telemetry cannot cover the action.
- `error: true` changes labels and captions, but stays calm. Add
  `errorMotion: true` only when a shake genuinely clarifies the failure.
- Reduced-motion mode removes camera travel and shakes.

## Privacy

- On private account/admin surfaces, treat emails, passwords, tokens,
  tenant/object IDs, customer or tenant domains, raw SPA URLs, signed-in
  identity chips, and unrelated people as sensitive by default.
- Keep public source material—authors, post text, and link domains—when it is
  evidence for the task. Do not redact it solely because it is a username or
  domain.
- Use a short semantic `route`, never a raw trace URL.
- Add page-coordinate rectangles under `redact`. The renderer uses opaque
  masks with padding; blur and pixelation are not safe enough for secrets.
- Match masks to the surrounding surface when possible. `privacy.mask` sets a
  quiet default; a rectangle can override `fill`, `stroke`, `radius`, and `pad`.
  Colors must be opaque six-digit hex values.
- Redaction remains active across both `frame` and `after` states.
- List a frame in `privacy.reviewedFrames` only after inspecting the rendered,
  masked image at full resolution. The renderer blocks export otherwise.
- Sensitive synthetic typing must set `type.redact: true`.

## Authenticity

- Preserve raw captured frames, cursor motion, clicks, and typing as evidence.
- Keep subtitles and chapter progress outside the captured app surface. Do not
  paint explanatory labels over raw frames.
- Use the native system font and `frameStyle: "native"`. Never invent a URL,
  tab title, browser state, timestamp, user value, or successful result.
- Synthetic browser chrome is blocked unless the composition explicitly sets
  `authenticity.allowSyntheticChrome: true`.
- Let narration persist while screenshots advance when one thought spans
  multiple actions; text and frames do not need to change together.

## Edit brief

Read `skills/browser-harness-video/references/edit-brief.md`. Choose the causal
story, one-based recording events, semantic routes, narration, verified
outcomes, and page-coordinate redactions. Do not choose durations, camera
coordinates, zoom, motion, typography, browser chrome, cursor size, or colors.
The compiler rejects those fields so every new session inherits the v9 cut.

## Workflow

From the repository root:

```bash
uv run skills/browser-harness-video/scripts/init_video.py <recording-dir>
```

Read `recording-summary.json`, inspect the source frames, and write
`edit-brief.json`. Compile and audit it:

```bash
uv run skills/browser-harness-video/scripts/compose_video.py <recording-dir>
uv run skills/browser-harness-video/scripts/audit_video.py <recording-dir>
```

Never hand-edit generated `composition.js`; fix the brief or the shared
compiler instead.

Inspect `privacy-contact-sheet.jpg` and every masked image in
`.privacy-review/` locally. Never share those review artifacts. Fix every
error before renderer review.

Generate the normal-motion, reduced-motion, and exact-click review sheets:

```bash
uv run skills/browser-harness-video/scripts/render_video.py review <recording-dir>
```

The script opens `video.html` through the local harness with recording disabled,
runs `window.videoPreflight()` and `window.clickVisibility()`, and captures every
required state. Inspect every generated `renderer-*-contact-sheet.jpg`.

Only after inspecting those sheets, export the verified MP4:

```bash
uv run skills/browser-harness-video/scripts/render_video.py export <recording-dir> --reviewed
```

The script exports in real time, converts to H.264, fully decodes the result,
checks its duration, and creates `renderer-final-contact-sheet.jpg`. Inspect
that final sheet before sharing `video.mp4`.
