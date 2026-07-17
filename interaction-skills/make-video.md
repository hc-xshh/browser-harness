# Make a video

Use captured frames as evidence. Never reenact a finished task or fabricate a
cleaner result.

## Workflow

Use the exact recording selected under `SKILL.md`; never replay browser work to
manufacture missing footage. For a post-task recording, verify `meta.json` and
`events.jsonl` match the task.

```bash
browser-harness video init <recording> --require-explicit
# write <recording>/edit-brief.json
browser-harness video review <recording>
# inspect video-review-contact-sheet.jpg and every image in .privacy-review/
browser-harness video export <recording> --reviewed
```

Omit `--require-explicit` only for a verified post-task recording. In a source
checkout use `./browser-harness`. Never edit generated `composition.js` or
`video.html`; change the brief or shared implementation. Export never
overwrites an existing video, so use `--output video-v2.mp4` for another cut.

## Edit brief

Events are one-based entries in `recording-summary.json`; chapters are
zero-based plan entries. `frameEvent` may select a cleaner pre-action frame and
`afterEvent` should show the click result.

```json
{
  "task": "Extract the top five stories and comments",
  "summary": "Collect each discussion and save structured JSON.",
  "plan": ["Collect stories", "Capture discussions", "Verify JSON"],
  "actions": [
    {
      "event": 3,
      "frameEvent": 2,
      "afterEvent": 4,
      "chapter": 0,
      "route": "Hacker News / Front page",
      "afterRoute": "Hacker News / Discussion",
      "narration": "Open the first discussion.",
      "label": "Open discussion"
    }
  ],
  "explanations": [{
    "afterAction": 1,
    "title": "Why the first approach failed",
    "observed": "Navigation links appeared in the result",
    "mistake": "I selected every page link",
    "correction": "Restrict extraction to story rows"
  }],
  "outcomeTitle": "Five discussions captured",
  "outcomeSummary": "The requested JSON is verified.",
  "outcomes": ["Five current stories saved", "Comment trees preserved"],
  "privacy": {
    "reviewedFrames": ["0002.jpg", "0004.jpg"],
    "redact": {"0004.jpg": [{"x": 10, "y": 10, "w": 120, "h": 32}]}
  }
}
```

Keep only actions that change the viewer's understanding. Each action requires
`event`, `chapter`, and a short semantic `route`; optional fields are
`frameEvent`, `afterEvent`, `afterRoute`, `narration`, `label`, `detour`,
`error`, `context`, and `showTyping`. Narration is at most seven words.
Explanations reveal Observed → Mistake → Correction. Outcomes must be verified.

Typed text is hidden unless inspected and explicitly enabled with
`showTyping: true`; passwords cannot be revealed. Private app URLs, identities,
credentials, tokens, tenant data, and unrelated people stay private. Use opaque
redaction rectangles in page coordinates and list every used frame in
`privacy.reviewedFrames` only after inspecting its final full-resolution image.
The detector is a backstop, not a privacy guarantee.
