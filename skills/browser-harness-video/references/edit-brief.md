# Edit brief

Write only editorial decisions to `edit-brief.json`. The compiler owns camera
coordinates, zoom, motion, typography, colors, duration, cursor size, click
timing, browser chrome, and card layout.

```json
{
  "task": "Extract the top five stories and comments",
  "summary": "Collect each discussion and save structured JSON.",
  "plan": ["Collect top stories", "Capture discussions", "Verify the JSON"],
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
    },
    {
      "event": 8,
      "chapter": 1,
      "route": "Hacker News / Discussion",
      "narration": "Capture the complete comment tree.",
      "label": "Read comments"
    }
  ],
  "explanations": [
    {
      "afterAction": 1,
      "title": "Why the first approach failed",
      "summary": "The page had loaded, but the selector was too broad.",
      "observed": "Unrelated navigation links were included",
      "mistake": "I selected every link on the page",
      "correction": "Restrict extraction to story rows"
    }
  ],
  "outcomeTitle": "Five discussions captured",
  "outcomeSummary": "The requested JSON is complete and verified.",
  "outcomes": ["Five current stories saved", "Comment trees preserved"],
  "privacy": {
    "reviewedFrames": ["0003.jpg", "0004.jpg", "0008.jpg"],
    "redact": {
      "0008.jpg": [{"x": 10, "y": 10, "w": 120, "h": 32}]
    }
  }
}
```

Rules:

- `event`, `frameEvent`, and `afterEvent` are one-based entries in
  `recording-summary.json`. `event` supplies authentic action coordinates and
  telemetry. `frameEvent` optionally chooses the clean pre-action frame;
  otherwise it defaults to `event`.
- An action needs `event`, `chapter`, and a short semantic `route`.
- Use `afterEvent` for the visible consequence of a click. The compiler shows it
  in the same beat with sub-80ms feedback.
- The compiler adds a brief evidence hold whenever a raw browser beat is
  followed by an explanation or outcome card. Do not author timing for it.
- Narration is optional, sticky, and at most ten words; prefer seven. Set it
  only when the thought changes, normally once for two or three actions.
- Use `context: true` only for a deliberate full-page orientation shot. The
  compiler otherwise follows authentic cursor or typing coordinates.
- `explanations` are optional. Each is inserted after the numbered action and
  always renders Observed, Mistake, Correction in sequence.
- List only achieved, verified outcomes. Never turn an intention into success.
- `privacy.reviewedFrames` must cover every used source and result frame after
  inspecting the final opaque masks at full resolution.
- Public authors, post text, and link domains are task evidence, not secrets.
  Redact private account/customer identity or actual sensitive values.
- Redaction coordinates are page CSS pixels. A rectangle may additionally set
  `fill`, `stroke`, `radius`, or `pad`.
- Do not add `dur`, `zoom`, `followScale`, `wide`, `cameraCut`, `frameStyle`,
  `motion`, `bg`, font, cursor, or click coordinates. The compiler rejects
  unknown fields instead of silently accepting visual drift.
- A normal cut must fit the compiler's 22-second budget. If it does not, shorten
  card copy, remove redundant actions, or reuse narration. Do not seek an
  exception merely so every detail can remain on screen; viewers can pause.
