#!/usr/bin/env python3
"""Block unsafe video exports and create a local privacy contact sheet."""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


DANGEROUS_ROUTE = re.compile(
    r"@|[?#]|onmicrosoft|(?:tenant|user|object)[_-]?id|"
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)
OPAQUE_HEX = re.compile(r"^#[0-9a-f]{6}$", re.IGNORECASE)
STYLE_PATH = Path(__file__).resolve().parents[1] / "assets" / "house-style-v9.json"


def house_style() -> dict:
    return json.loads(STYLE_PATH.read_text(encoding="utf-8"))


def load_composition(path: Path) -> dict:
    loader = r"""
const fs = require('fs');
const vm = require('vm');
const file = process.argv[1];
const sandbox = {window: {}};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(file, 'utf8'), sandbox, {filename: file});
process.stdout.write(JSON.stringify(sandbox.window.COMPOSITION));
"""
    proc = subprocess.run(
        ["node", "-e", loader, str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode or not proc.stdout:
        raise RuntimeError(proc.stderr.strip() or "composition did not set window.COMPOSITION")
    return json.loads(proc.stdout)


def words(value: object) -> int:
    return len(re.findall(r"\S+", str(value or "")))


def card_text(beat: dict, plan: list) -> str:
    details: list[object] = []
    if beat.get("kind") == "intro":
        details = plan
    elif beat.get("kind") == "explanation":
        details = [
            value
            for point in beat.get("points") or []
            for value in (point.get("label"), point.get("text"))
        ]
    elif beat.get("kind") == "outcome":
        details = beat.get("outcomes") or []
    return " ".join(
        str(value)
        for value in (beat.get("title"), beat.get("sub"), *details)
        if value
    )


def card_target_seconds(beat: dict, plan: list, reading_wpm: float) -> float:
    base = 4.5 if beat.get("kind") in {"intro", "outcome"} else 4.0
    if beat.get("kind") not in {"intro", "outcome", "explanation"}:
        base = 3.5
    return max(base, 0.4 + words(card_text(beat, plan)) * 60 / reading_wpm)


def used_frames(beats: list[dict]) -> list[str]:
    ordered = []
    for beat in beats:
        for key in ("frame", "after"):
            value = beat.get(key)
            if value and value not in ordered:
                ordered.append(value)
    return ordered


def duration_budget(beats: list[dict], pacing: dict) -> float:
    actions = sum(not beat.get("card") for beat in beats)
    explanations = sum(beat.get("kind") == "explanation" for beat in beats)
    raw_to_card = sum(
        bool(not beat.get("card") and next_beat.get("card"))
        for beat, next_beat in zip(beats, beats[1:])
    )
    budget = float(pacing["baseDurationBudget"])
    budget += max(0, actions - 5) * float(pacing["extraActionSeconds"])
    budget += max(0, explanations - 1) * float(
        pacing["extraExplanationSeconds"]
    )
    budget += raw_to_card * float(pacing["rawToCardHoldSeconds"])
    return round(min(budget, float(pacing["maximumDurationBudget"])), 3)


def validate(recording: Path, comp: dict) -> tuple[list[str], list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    beats = comp.get("beats") or []
    frames = used_frames(beats)
    plan = comp.get("plan") or []
    style = house_style()
    expected = {
        "houseStyleVersion": style["version"],
        "frameStyle": style["frameStyle"],
        "readingWpm": style["readingWpm"],
        "pacing": style["pacing"],
        "bg": style["background"],
        "motion": style["motion"],
    }
    for field, value in expected.items():
        if comp.get(field) != value:
            errors.append(f"{field} must match generated v9 house style")
    if not 2 <= len(plan) <= 5:
        errors.append("plan must contain 2–5 steps")
    if not beats:
        errors.append("composition has no beats")
        return errors, warnings, frames
    budget = duration_budget(beats, style["pacing"])
    if comp.get("durationBudget") != budget:
        errors.append("durationBudget must match generated v9 pacing")
    duration = sum(float(beat.get("dur") or 0) for beat in beats)
    if duration > budget + 0.001:
        errors.append(
            f"video is {duration:.1f}s; shorten it to the {budget:.1f}s budget"
        )
    if beats[0].get("kind") != "intro" or not beats[0].get("card"):
        errors.append("first beat must be an intro card")
    elif float(beats[0].get("dur") or 0) < 4:
        errors.append("intro card must remain visible for at least 4 seconds")
    if beats[-1].get("kind") != "outcome" or not beats[-1].get("card"):
        errors.append("last beat must be an explicit outcome card")
    elif not beats[-1].get("outcomes"):
        errors.append("outcome card must list achieved outcomes")

    for index, beat in enumerate(beats, 1):
        if beat.get("card"):
            reading_wpm = float(comp.get("readingWpm") or 380)
            target = card_target_seconds(beat, plan, reading_wpm)
            duration = float(beat.get("dur") or 0)
            if duration + 0.001 < target:
                errors.append(f"beat {index}: card is shorter than its structured scan target")
            if duration > target + 1.001 and not str(beat.get("linger") or "").strip():
                errors.append(f"beat {index}: card is overlong; shorten it or add a linger reason")
            if beat.get("kind") == "explanation":
                labels = [str(point.get("label") or "").lower() for point in beat.get("points") or []]
                if labels != ["observed", "mistake", "correction"]:
                    errors.append(
                        f"beat {index}: explanation must be Observed, Mistake, Correction"
                    )
        text = beat.get("narration") or beat.get("caption")
        count = words(text)
        if count > 10:
            errors.append(f"beat {index}: narration has {count} words; maximum is 10")
        elif count > 7:
            warnings.append(f"beat {index}: narration has {count} words; target is 7")
        if not beat.get("card"):
            chapter = beat.get("chapter")
            if not isinstance(chapter, int) or not 0 <= chapter < len(plan):
                errors.append(f"beat {index}: chapter must index the plan")
            route = beat.get("route")
            if not route:
                errors.append(f"beat {index}: use a semantic route label")
            elif DANGEROUS_ROUTE.search(str(route)):
                errors.append(f"beat {index}: route contains sensitive/raw URL material")
            after_route = beat.get("afterRoute")
            if after_route and DANGEROUS_ROUTE.search(str(after_route)):
                errors.append(f"beat {index}: afterRoute contains sensitive/raw URL material")
            if beat.get("url"):
                errors.append(f"beat {index}: raw url is forbidden; use route")
            if beat.get("click") and not beat.get("after"):
                warnings.append(f"beat {index}: click has no in-beat result frame")
            typed = (beat.get("type") or {}).get("text")
            if typed and DANGEROUS_ROUTE.search(str(typed)) and not (beat.get("type") or {}).get("redact"):
                errors.append(f"beat {index}: sensitive typing overlay must set redact: true")
            if (
                index < len(beats)
                and beats[index].get("card")
                and float(beat.get("endStateHold") or 0)
                < float(style["pacing"]["rawToCardHoldSeconds"])
            ):
                errors.append(
                    f"beat {index}: raw end state must hold before the next text card"
                )

    motion = comp.get("motion") or {}
    if (
        comp.get("frameStyle", "native") == "browser"
        and (comp.get("authenticity") or {}).get("allowSyntheticChrome") is not True
    ):
        errors.append(
            "synthetic browser chrome requires authenticity.allowSyntheticChrome=true"
        )
    if float(motion.get("reactionLag", 0.025)) > 0.04:
        warnings.append("reactionLag exceeds 40ms")
    if float(motion.get("reactionFade", 0.04)) > 0.06:
        warnings.append("reactionFade exceeds 60ms")
    if float(motion.get("wideScale", 0.8)) > 0.9:
        warnings.append("wideScale is not wide enough to restore context")

    for frame in frames:
        if not (recording / frame).is_file():
            errors.append(f"missing frame: {frame}")
    reviewed = set((comp.get("privacy") or {}).get("reviewedFrames") or [])
    missing_review = [frame for frame in frames if frame not in reviewed]
    if missing_review:
        errors.append("privacy review missing: " + ", ".join(missing_review))
    extra_review = sorted(reviewed - set(frames))
    if extra_review:
        warnings.append("privacy review lists unused frames: " + ", ".join(extra_review))
    redactions = comp.get("redact") or {}
    mask = (comp.get("privacy") or {}).get("mask") or {}
    for frame in frames:
        for index, rect in enumerate(redactions.get(frame, []), 1):
            fill = rect.get("fill", mask.get("fill", "#f2f4f7"))
            stroke = rect.get("stroke", mask.get("stroke", "#e2e7ec"))
            if not isinstance(fill, str) or not OPAQUE_HEX.fullmatch(fill):
                errors.append(f"{frame} mask {index} fill must be opaque six-digit hex")
            if stroke and (not isinstance(stroke, str) or not OPAQUE_HEX.fullmatch(stroke)):
                errors.append(f"{frame} mask {index} stroke must be opaque six-digit hex")
    return errors, warnings, frames


def masked_frame(recording: Path, comp: dict, frame: str) -> Image.Image:
    viewport = comp.get("viewport") or {}
    vw, vh = float(viewport.get("w") or 1), float(viewport.get("h") or 1)
    redactions = comp.get("redact") or {}
    privacy = comp.get("privacy") or {}
    mask = privacy.get("mask") or {}
    pad = float(privacy.get("pad") or 8)
    image = Image.open(recording / frame).convert("RGB")
    sx, sy = image.width / vw, image.height / vh
    frame_draw = ImageDraw.Draw(image)
    for rect in redactions.get(frame, []):
        rect_pad = float(rect.get("pad", pad))
        x0 = max(0, (float(rect["x"]) - rect_pad) * sx)
        y0 = max(0, (float(rect["y"]) - rect_pad) * sy)
        x1 = min(image.width, (float(rect["x"]) + float(rect["w"]) + rect_pad) * sx)
        y1 = min(image.height, (float(rect["y"]) + float(rect["h"]) + rect_pad) * sy)
        fill = rect.get("fill", mask.get("fill", "#f2f4f7"))
        stroke = rect.get("stroke", mask.get("stroke", "#e2e7ec"))
        radius = float(rect.get("radius", mask.get("radius", 7))) * min(sx, sy)
        frame_draw.rounded_rectangle(
            (x0, y0, x1, y1),
            radius=radius,
            fill=fill,
            outline=stroke or None,
            width=max(1, round(min(sx, sy))),
        )
    return image


def contact_sheet(recording: Path, comp: dict, frames: list[str], output: Path) -> Path:
    redactions = comp.get("redact") or {}
    thumb = (440, 280)
    label_h, banner_h, gap, cols = 42, 52, 12, 3
    rows = max(1, math.ceil(len(frames) / cols))
    sheet = Image.new(
        "RGB",
        (cols * thumb[0] + (cols + 1) * gap, banner_h + rows * (thumb[1] + label_h + gap) + gap),
        "#171a20",
    )
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    draw.text((gap, 18), "LOCAL PRIVACY REVIEW — DO NOT SHARE", fill="#ffffff", font=font)
    review_dir = recording / ".privacy-review"
    review_dir.mkdir(exist_ok=True)
    for stale in review_dir.glob("*.jpg"):
        stale.unlink()
    for index, frame in enumerate(frames):
        image = masked_frame(recording, comp, frame)
        image.save(review_dir / frame, quality=94)
        preview = ImageOps.contain(image, thumb, Image.Resampling.LANCZOS)
        col, row = index % cols, index // cols
        x = gap + col * thumb[0]
        y = banner_h + gap + row * (thumb[1] + label_h + gap)
        sheet.paste(preview, (x + (thumb[0] - preview.width) // 2, y))
        draw.text(
            (x, y + thumb[1] + 8),
            f"{frame}  masks:{len(redactions.get(frame, []))}",
            fill="#d7dbe3",
            font=font,
        )
    sheet.save(output, quality=90)
    return review_dir


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("recording", type=Path)
    parser.add_argument("--composition", default="composition.js")
    args = parser.parse_args()
    recording = args.recording.expanduser().resolve()
    composition_path = recording / args.composition
    if not composition_path.is_file():
        parser.error(f"missing {composition_path}")
    comp = load_composition(composition_path)
    errors, warnings, frames = validate(recording, comp)
    sheet = recording / "privacy-contact-sheet.jpg"
    review_dir = contact_sheet(recording, comp, frames, sheet)
    report = {
        "errors": errors,
        "warnings": warnings,
        "frames": frames,
        "contactSheet": str(sheet),
        "reviewDir": str(review_dir),
    }
    (recording / "video-audit.json").write_text(json.dumps(report, indent=2) + "\n")
    for warning in warnings:
        print(f"WARN: {warning}")
    for error in errors:
        print(f"ERROR: {error}")
    print(f"privacy contact sheet: {sheet}")
    print(f"full-resolution review: {review_dir}")
    print(f"preflight: {len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
