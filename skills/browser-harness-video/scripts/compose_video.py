#!/usr/bin/env python3
"""Compile editorial choices into the deterministic browser video house style."""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any


SKILL = Path(__file__).resolve().parents[1]
STYLE_PATH = SKILL / "assets" / "house-style-v9.json"
ACTION_KEYS = {
    "event",
    "frameEvent",
    "afterEvent",
    "chapter",
    "route",
    "afterRoute",
    "narration",
    "label",
    "detour",
    "error",
    "context",
}
BRIEF_KEYS = {
    "task",
    "summary",
    "plan",
    "actions",
    "explanations",
    "outcomeTitle",
    "outcomeSummary",
    "outcomes",
    "privacy",
}
PRIVACY_KEYS = {"reviewedFrames", "redact"}
EXPLANATION_KEYS = {
    "afterAction",
    "title",
    "summary",
    "observed",
    "mistake",
    "correction",
}
TYPE_HELPERS = {"type_text", "fill", "fill_input"}
CLICK_HELPERS = {"click_at_xy"}
ROUTE_UNSAFE = re.compile(
    r"@|[?#]|://|onmicrosoft|(?:tenant|user|object)[_-]?id|"
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)


class BriefError(ValueError):
    """An edit brief violates the deliberately small authoring contract."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BriefError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise BriefError(f"{path} must contain a JSON object")
    return value


def reject_unknown(value: dict[str, Any], allowed: set[str], where: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise BriefError(f"{where} has unsupported field(s): {', '.join(unknown)}")


def require_text(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BriefError(f"{where} must be non-empty text")
    return value.strip()


def require_text_list(value: Any, where: str, low: int, high: int) -> list[str]:
    if not isinstance(value, list) or not low <= len(value) <= high:
        raise BriefError(f"{where} must contain {low}–{high} items")
    return [require_text(item, f"{where}[{index}]") for index, item in enumerate(value)]


def words(value: Any) -> int:
    return len(re.findall(r"\S+", str(value or "")))


def card_duration(
    title: str,
    summary: str | None,
    details: list[str],
    kind: str,
    reading_wpm: float,
) -> float:
    text = " ".join(part for part in (title, summary, *details) if part)
    base = 4.5 if kind in {"intro", "outcome"} else 4.0
    return round(max(base, 0.4 + words(text) * 60 / reading_wpm), 3)


def validate_narration(value: Any, where: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise BriefError(f"{where} must be text")
    if words(value) > 10:
        raise BriefError(f"{where} exceeds ten words")
    return value.strip()


def optional_text(value: Any, where: str) -> str | None:
    if value is None:
        return None
    return require_text(value, where)


def event_at(events: list[dict[str, Any]], number: Any, where: str) -> dict[str, Any]:
    if not isinstance(number, int) or isinstance(number, bool):
        raise BriefError(f"{where} must be a one-based integer")
    if number < 1 or number > len(events):
        raise BriefError(f"{where} is outside recording-summary.json")
    event = events[number - 1]
    if not event.get("frame"):
        raise BriefError(f"{where} has no captured frame")
    return event


def event_target(event: dict[str, Any]) -> dict[str, float] | None:
    cursor = event.get("cursor")
    if isinstance(cursor, dict) and cursor.get("x") is not None and cursor.get("y") is not None:
        return {"x": float(cursor["x"]), "y": float(cursor["y"])}
    box = event.get("box")
    if isinstance(box, dict) and all(box.get(key) is not None for key in ("x", "y", "w", "h")):
        return {
            "x": float(box["x"]) + float(box["w"]) * 0.3,
            "y": float(box["y"]) + float(box["h"]) / 2,
        }
    return None


def default_action_duration(beat: dict[str, Any], pacing: dict[str, Any]) -> float:
    base = 0.7
    if beat.get("click"):
        base = 1.15
    if beat.get("after"):
        base = max(base, 1.4)
    typing = beat.get("type")
    if typing:
        base = max(base, 0.6 + len(str(typing.get("text") or "")) * 0.035)
    narration = beat.get("narration")
    if narration:
        base = max(
            base,
            float(pacing["captionBaseSeconds"])
            + float(pacing["captionSecondsPerWord"]) * words(narration),
        )
    return round(base, 3)


def duration_budget(
    action_count: int,
    explanation_count: int,
    raw_to_card_count: int,
    pacing: dict[str, Any],
) -> float:
    budget = float(pacing["baseDurationBudget"])
    budget += max(0, action_count - 5) * float(pacing["extraActionSeconds"])
    budget += max(0, explanation_count - 1) * float(
        pacing["extraExplanationSeconds"]
    )
    budget += raw_to_card_count * float(pacing["rawToCardHoldSeconds"])
    return round(min(budget, float(pacing["maximumDurationBudget"])), 3)


def add_raw_to_card_holds(beats: list[dict[str, Any]], pacing: dict[str, Any]) -> int:
    hold = float(pacing["rawToCardHoldSeconds"])
    count = 0
    for beat, next_beat in zip(beats, beats[1:]):
        if beat.get("card") or not next_beat.get("card"):
            continue
        beat["endStateHold"] = hold
        beat["dur"] = round(float(beat["dur"]) + hold, 3)
        count += 1
    return count


def compile_action(
    action: dict[str, Any],
    index: int,
    events: list[dict[str, Any]],
    plan: list[str],
    first_ts: float,
    previous_target: dict[str, float] | None,
    viewport: dict[str, float],
    pacing: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, float] | None]:
    if not isinstance(action, dict):
        raise BriefError(f"actions[{index}] must be an object")
    reject_unknown(action, ACTION_KEYS, f"actions[{index}]")
    event = event_at(events, action.get("event"), f"actions[{index}].event")
    frame_event = event
    if action.get("frameEvent") is not None:
        frame_event = event_at(
            events, action["frameEvent"], f"actions[{index}].frameEvent"
        )
    chapter = action.get("chapter")
    if not isinstance(chapter, int) or isinstance(chapter, bool) or not 0 <= chapter < len(plan):
        raise BriefError(f"actions[{index}].chapter must index plan")
    route = require_text(action.get("route"), f"actions[{index}].route")
    if ROUTE_UNSAFE.search(route):
        raise BriefError(f"actions[{index}].route must be semantic, not a raw URL or identity")

    beat: dict[str, Any] = {
        "frame": frame_event["frame"],
        "route": route,
        "chapter": chapter,
    }
    after_number = action.get("afterEvent")
    if after_number is not None:
        after = event_at(events, after_number, f"actions[{index}].afterEvent")
        beat["after"] = after["frame"]
        after_route = action.get("afterRoute")
        if after_route is not None:
            after_route = require_text(after_route, f"actions[{index}].afterRoute")
            if ROUTE_UNSAFE.search(after_route):
                raise BriefError(f"actions[{index}].afterRoute must be semantic")
            beat["afterRoute"] = after_route

    narration = validate_narration(action.get("narration"), f"actions[{index}].narration")
    if narration is not None:
        beat["narration"] = narration
    if action.get("label") is not None:
        beat["label"] = require_text(action["label"], f"actions[{index}].label")
    if action.get("detour") is True:
        beat["detour"] = True
    if action.get("error") is True:
        beat["error"] = True

    helper = str(event.get("helper") or "")
    cursor = event.get("cursor")
    if helper in CLICK_HELPERS:
        if not isinstance(cursor, dict) or cursor.get("x") is None or cursor.get("y") is None:
            raise BriefError(f"actions[{index}] identifies a click without captured coordinates")
        beat["cursor"] = {"x": cursor["x"], "y": cursor["y"]}
        beat["click"] = True
    elif helper in TYPE_HELPERS:
        box = event.get("box")
        text = event.get("text")
        if (
            not isinstance(box, dict)
            or not all(box.get(key) is not None for key in ("x", "y", "w", "h"))
            or text is None
        ):
            raise BriefError(f"actions[{index}] identifies typing without a captured box and text")
        beat["type"] = {
            "box": {key: box[key] for key in ("x", "y", "w", "h")},
            "text": str(text),
            **({"redact": True} if event.get("sensitive") else {}),
        }

    target = event_target(event)
    if action.get("context") is True and not (beat.get("click") or beat.get("type")):
        beat["wide"] = True
    elif target and previous_target:
        distance = math.hypot(target["x"] - previous_target["x"], target["y"] - previous_target["y"])
        diagonal = math.hypot(float(viewport["w"]), float(viewport["h"]))
        if distance > diagonal * 0.58:
            beat["cameraCut"] = True

    ts = event.get("ts")
    if isinstance(ts, (int, float)):
        beat["t"] = round(max(0.0, float(ts) - first_ts), 3)
    beat["dur"] = default_action_duration(beat, pacing)
    return beat, target or previous_target


def compile_brief(summary: dict[str, Any], brief: dict[str, Any], style: dict[str, Any]) -> dict[str, Any]:
    reject_unknown(brief, BRIEF_KEYS, "edit brief")
    task = require_text(brief.get("task"), "task")
    summary_text = optional_text(brief.get("summary"), "summary")
    plan = require_text_list(brief.get("plan"), "plan", 2, 5)
    outcomes = require_text_list(brief.get("outcomes"), "outcomes", 1, 5)
    actions = brief.get("actions")
    if not isinstance(actions, list) or not actions:
        raise BriefError("actions must contain at least one action")
    events = summary.get("events")
    if not isinstance(events, list) or not events:
        raise BriefError("recording-summary.json has no events")
    viewport_event = next(
        (event for event in events if (event.get("viewport") or {}).get("w") and (event.get("viewport") or {}).get("h")),
        None,
    )
    if not viewport_event:
        raise BriefError("recording-summary.json has no viewport")
    viewport = viewport_event["viewport"]
    first_ts = next(
        (float(event["ts"]) for event in events if isinstance(event.get("ts"), (int, float))),
        0.0,
    )

    privacy = brief.get("privacy")
    if not isinstance(privacy, dict):
        raise BriefError("privacy must be an object")
    reject_unknown(privacy, PRIVACY_KEYS, "privacy")
    reviewed = privacy.get("reviewedFrames")
    if not isinstance(reviewed, list) or not all(isinstance(frame, str) for frame in reviewed):
        raise BriefError("privacy.reviewedFrames must be a list of frame names")
    redact = privacy.get("redact") or {}
    if not isinstance(redact, dict):
        raise BriefError("privacy.redact must be an object")

    explanations = brief.get("explanations") or []
    if not isinstance(explanations, list):
        raise BriefError("explanations must be a list")
    pacing = style["pacing"]
    reading_wpm = float(style["readingWpm"])
    explanation_by_action: dict[int, list[dict[str, Any]]] = {}
    for index, explanation in enumerate(explanations):
        if not isinstance(explanation, dict):
            raise BriefError(f"explanations[{index}] must be an object")
        reject_unknown(explanation, EXPLANATION_KEYS, f"explanations[{index}]")
        after_action = explanation.get("afterAction")
        if not isinstance(after_action, int) or isinstance(after_action, bool) or not 1 <= after_action <= len(actions):
            raise BriefError(f"explanations[{index}].afterAction must index actions")
        title = require_text(explanation.get("title"), f"explanations[{index}].title")
        sub = optional_text(explanation.get("summary"), f"explanations[{index}].summary")
        points = [
            {"label": "Observed", "text": require_text(explanation.get("observed"), f"explanations[{index}].observed")},
            {"label": "Mistake", "text": require_text(explanation.get("mistake"), f"explanations[{index}].mistake")},
            {"label": "Correction", "text": require_text(explanation.get("correction"), f"explanations[{index}].correction")},
        ]
        card = {
            "card": True,
            "kind": "explanation",
            "title": title,
            **({"sub": sub} if sub is not None else {}),
            "points": points,
            "dur": card_duration(
                title,
                sub,
                [part for point in points for part in (point["label"], point["text"])],
                "explanation",
                reading_wpm,
            ),
        }
        explanation_by_action.setdefault(after_action, []).append(card)

    intro = {
        "card": True,
        "kind": "intro",
        "title": task,
        **({"sub": summary_text} if summary_text is not None else {}),
        "dur": card_duration(task, summary_text, plan, "intro", reading_wpm),
    }
    beats: list[dict[str, Any]] = [intro]
    previous_target = None
    for index, action in enumerate(actions):
        beat, previous_target = compile_action(
            action, index, events, plan, first_ts, previous_target, viewport, pacing
        )
        beats.append(beat)
        beats.extend(explanation_by_action.get(index + 1, []))

    outcome_title = require_text(brief.get("outcomeTitle") or "Task complete", "outcomeTitle")
    outcome_summary = optional_text(brief.get("outcomeSummary"), "outcomeSummary")
    beats.append(
        {
            "card": True,
            "kind": "outcome",
            "title": outcome_title,
            **({"sub": outcome_summary} if outcome_summary is not None else {}),
            "outcomes": outcomes,
            "dur": card_duration(
                outcome_title, outcome_summary, outcomes, "outcome", reading_wpm
            ),
        }
    )

    raw_to_card_count = add_raw_to_card_holds(beats, pacing)
    budget = duration_budget(
        len(actions), len(explanations), raw_to_card_count, pacing
    )
    duration = round(sum(float(beat["dur"]) for beat in beats), 3)
    if duration > budget + 0.001:
        raise BriefError(
            f"compiled video is {duration:.1f}s; v{style['version']} budget is "
            f"{budget:.1f}s. Shorten card copy, remove redundant actions, or set "
            "narration only when the thought changes; viewers can pause for detail"
        )

    house_privacy = style["privacy"]
    return {
        "houseStyleVersion": style["version"],
        "viewport": {"w": viewport["w"], "h": viewport["h"]},
        "cursorStart": style["cursorStart"],
        "frameStyle": style["frameStyle"],
        "readingWpm": style["readingWpm"],
        "pacing": pacing,
        "durationBudget": budget,
        "bg": style["background"],
        "plan": plan,
        "motion": style["motion"],
        "privacy": {
            "reviewedFrames": reviewed,
            "pad": house_privacy["pad"],
            "mask": house_privacy["mask"],
        },
        "redact": redact,
        "beats": beats,
    }


def write_composition(path: Path, composition: dict[str, Any]) -> None:
    body = json.dumps(composition, indent=2, ensure_ascii=False)
    path.write_text(f"window.COMPOSITION = {body};\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("recording", type=Path)
    parser.add_argument("--brief", default="edit-brief.json")
    parser.add_argument("--output", default="composition.js")
    args = parser.parse_args()
    recording = args.recording.expanduser().resolve()
    try:
        summary = load_json(recording / "recording-summary.json")
        brief = load_json(recording / args.brief)
        style = load_json(STYLE_PATH)
        composition = compile_brief(summary, brief, style)
        write_composition(recording / args.output, composition)
    except BriefError as exc:
        parser.error(str(exc))
    print(f"composition: {recording / args.output}")
    print(f"house style: v{composition['houseStyleVersion']}")
    print(f"beats: {len(composition['beats'])}")
    print(
        "duration: "
        f"{sum(beat['dur'] for beat in composition['beats']):.1f}s / "
        f"{composition['durationBudget']:.1f}s budget"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
