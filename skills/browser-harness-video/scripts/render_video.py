#!/usr/bin/env python3
"""Prepare compact renderer review sheets, then export and verify an MP4."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import math
import os
import shutil
import subprocess
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = ROOT / "interaction-skills" / "video-template.html"
MARKER = "__BH_VIDEO_RESULT__="


def load_composition(recording: Path) -> dict:
    path = recording / "composition.js"
    text = path.read_text(encoding="utf-8").strip()
    prefix = "window.COMPOSITION ="
    if not text.startswith(prefix):
        raise RuntimeError(f"{path} is not a generated composition")
    return json.loads(text[len(prefix):].strip().removesuffix(";"))


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def review_samples(comp: dict) -> list[dict]:
    """One stable state per beat, plus every explanation reveal."""
    samples = []
    start = 0.0
    for index, beat in enumerate(comp.get("beats") or [], 1):
        duration = float(beat.get("dur") or 0)
        if beat.get("kind") == "explanation" and beat.get("points"):
            points = beat["points"]
            first, final_hold = 1.1, 3.0
            span = max(0.0, duration - first - final_hold)
            gap = span / max(1, len(points) - 1)
            for point_index, point in enumerate(points, 1):
                local = min(max(0.05, duration - 0.05), first + (point_index - 1) * gap + 0.2)
                samples.append({
                    "time": round(start + local, 3),
                    "label": f"beat {index} · {point.get('label') or point_index}",
                })
        else:
            local = min(max(0.05, duration - 0.05), 1.0 if beat.get("card") else max(0.12, min(0.5, duration / 2)))
            samples.append({"time": round(start + local, 3), "label": f"beat {index}"})
        start += duration
    return samples


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, _format, *_args):
        pass


@contextlib.contextmanager
def serve(recording: Path):
    handler = lambda *args, **kwargs: _QuietHandler(  # noqa: E731
        *args, directory=str(recording), **kwargs
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/video.html"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _harness_command() -> list[str]:
    local = ROOT / "browser-harness"
    if local.is_file():
        return [str(local)]
    installed = shutil.which("browser-harness")
    if installed:
        return [installed]
    raise RuntimeError("browser-harness command not found")


def run_harness(code: str, timeout: float = 60) -> dict:
    env = {**os.environ, "BH_RECORD": "0"}
    proc = subprocess.run(
        _harness_command(),
        input=code,
        text=True,
        capture_output=True,
        cwd=ROOT,
        env=env,
        timeout=timeout,
        check=False,
    )
    if proc.returncode:
        detail = (proc.stderr or proc.stdout).strip()
        raise RuntimeError(f"browser review failed: {detail}")
    for line in reversed(proc.stdout.splitlines()):
        if line.startswith(MARKER):
            return json.loads(line[len(MARKER):])
    raise RuntimeError(f"browser review returned no result: {proc.stdout[-1000:]}")


def _review_browser(recording: Path, url: str, samples: list[dict]) -> dict:
    review_dir = recording / ".renderer-review"
    payload = {
        "url": url,
        "samples": samples,
        "reviewDir": str(review_dir),
        "marker": MARKER,
    }
    code = f"""
import json, os, time
cfg = json.loads({json.dumps(json.dumps(payload))})
os.makedirs(cfg['reviewDir'], exist_ok=True)

def ready():
    for _ in range(100):
        if js('window.videoReady && window.videoReady()'):
            return
        time.sleep(0.05)
    raise RuntimeError('video assets did not become ready')

def inspect_mode(name, reduced):
    features = [{{'name':'prefers-reduced-motion','value':'reduce'}}] if reduced else []
    cdp('Emulation.setEmulatedMedia', media='', features=features)
    cdp('Page.reload', ignoreCache=True)
    wait_for_load()
    ready()
    preflight = js('window.videoPreflight()')
    clicks = js('window.clickVisibility()')
    captures = []
    for index, sample in enumerate(cfg['samples'], 1):
        js(f"window.seek({{sample['time']}})")
        path = f"{{cfg['reviewDir']}}/{{name}}-beat-{{index:02d}}.png"
        capture_screenshot(path)
        captures.append({{'path': path, 'time': sample['time'], 'label': sample['label']}})
    click_captures = []
    for index, click in enumerate(clicks, 1):
        for state, key in (('click', 'time'), ('result', 'resultTime')):
            js(f"window.seek({{click[key]}})")
            path = f"{{cfg['reviewDir']}}/{{name}}-click-{{index:02d}}-{{state}}.png"
            capture_screenshot(path)
            click_captures.append({{
                'path': path, 'time': click[key],
                'label': f"beat {{click['beat']}} · {{state}}",
            }})
    return {{'preflight': preflight, 'clicks': clicks, 'captures': captures,
            'clickCaptures': click_captures}}

target = new_tab(cfg['url'])
wait_for_load()
ready()
normal = inspect_mode('normal', False)
reduced = inspect_mode('reduced', True)
cdp('Emulation.setEmulatedMedia', media='', features=[])
close_tab(target)
print(cfg['marker'] + json.dumps({{'normal': normal, 'reduced': reduced}}))
"""
    return run_harness(code, timeout=max(60, len(samples) * 3))


def contact_sheet(captures: list[dict], output: Path, title: str) -> None:
    cols, tile_w, tile_h, label_h, gap, banner = 4, 400, 225, 34, 8, 42
    rows = max(1, math.ceil(len(captures) / cols))
    sheet = Image.new(
        "RGB",
        (cols * tile_w + (cols + 1) * gap, banner + rows * (tile_h + label_h + gap) + gap),
        "#171a20",
    )
    draw, font = ImageDraw.Draw(sheet), ImageFont.load_default()
    draw.text((gap, 15), title, fill="#ffffff", font=font)
    for index, capture in enumerate(captures):
        image = Image.open(capture["path"]).convert("RGB")
        preview = ImageOps.contain(image, (tile_w, tile_h), Image.Resampling.LANCZOS)
        col, row = index % cols, index // cols
        x, y = gap + col * (tile_w + gap), banner + gap + row * (tile_h + label_h + gap)
        sheet.paste(preview, (x + (tile_w - preview.width) // 2, y))
        label = f"{capture['label']}  {float(capture['time']):.2f}s"
        draw.text((x, y + tile_h + 9), label, fill="#d7dbe3", font=font)
    sheet.save(output, quality=91)


def _audit_ready(recording: Path) -> dict:
    audit_path = recording / "video-audit.json"
    composition = recording / "composition.js"
    if not audit_path.is_file():
        raise RuntimeError("run audit_video.py before renderer review")
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    if audit.get("errors"):
        raise RuntimeError("video audit has blocking errors")
    if audit_path.stat().st_mtime_ns < composition.stat().st_mtime_ns:
        raise RuntimeError("video audit is older than composition.js; rerun it")
    return audit


def review(recording: Path) -> int:
    started = time.monotonic()
    audit = _audit_ready(recording)
    comp = load_composition(recording)
    shutil.copy2(TEMPLATE, recording / "video.html")
    samples = review_samples(comp)
    review_dir = recording / ".renderer-review"
    review_dir.mkdir(exist_ok=True)
    for stale in review_dir.glob("*.png"):
        stale.unlink()
    with serve(recording) as url:
        result = _review_browser(recording, url, samples)

    errors = []
    for mode in ("normal", "reduced"):
        errors.extend(f"{mode}: {error}" for error in result[mode]["preflight"].get("errors", []))
        errors.extend(
            f"{mode}: beat {click['beat']} click is outside the safe viewport"
            for click in result[mode]["clicks"] if not click.get("visible")
        )
        sheet = recording / f"renderer-{mode}-contact-sheet.jpg"
        contact_sheet(result[mode]["captures"], sheet, f"{mode.upper()} MOTION — EVERY BEAT")
        result[mode]["contactSheet"] = str(sheet)

    click_captures = result["normal"]["clickCaptures"] + result["reduced"]["clickCaptures"]
    click_sheet = recording / "renderer-click-contact-sheet.jpg"
    if click_captures:
        contact_sheet(click_captures, click_sheet, "EXACT CLICK + RESULT STATES")

    report = {
        "errors": errors,
        "warnings": audit.get("warnings", []),
        "duration": round(sum(float(beat.get("dur") or 0) for beat in comp.get("beats") or []), 3),
        "compositionMtimeNs": (recording / "composition.js").stat().st_mtime_ns,
        "rendererSha256": file_hash(recording / "video.html"),
        "normal": result["normal"],
        "reduced": result["reduced"],
        "clickContactSheet": str(click_sheet) if click_captures else None,
        "elapsedSeconds": round(time.monotonic() - started, 3),
    }
    report_path = recording / "renderer-review.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"normal review:  {result['normal']['contactSheet']}")
    print(f"reduced review: {result['reduced']['contactSheet']}")
    if click_captures:
        print(f"click review:   {click_sheet}")
    print(f"renderer review: {len(errors)} error(s) in {report['elapsedSeconds']:.1f}s")
    return 1 if errors else 0


def _start_export(recording: Path, url: str, webm: Path) -> dict:
    payload = {"url": url, "downloadPath": str(recording), "filename": webm.name, "marker": MARKER}
    filename_js = json.dumps(webm.name)
    code = f"""
import json, time
cfg = json.loads({json.dumps(json.dumps(payload))})
target = new_tab(cfg['url'])
wait_for_load()
for _ in range(100):
    if js('window.videoReady && window.videoReady()'):
        break
    time.sleep(0.05)
else:
    raise RuntimeError('video assets did not become ready')
preflight = js('window.videoPreflight()')
clicks = js('window.clickVisibility()')
cdp('Browser.setDownloadBehavior', behavior='allow', downloadPath=cfg['downloadPath'], eventsEnabled=True)
cdp('Page.bringToFront')
started = js('''(() => {{
  window.__exported = null; window.__exportError = null;
  window.exportVideo({filename_js})
    .catch(error => window.__exportError = String(error));
  return true;
}})()''')
print(cfg['marker'] + json.dumps({{'target': target, 'preflight': preflight, 'clicks': clicks, 'started': started}}))
"""
    return run_harness(code, timeout=30)


def _close_editor(url: str) -> None:
    code = f"""
import json
url = {json.dumps(url)}
for tab in list_tabs():
    if tab.get('url') == url:
        close_tab(tab)
print({json.dumps(MARKER)} + json.dumps({{'closed': True}}))
"""
    try:
        run_harness(code, timeout=15)
    except Exception:
        pass


def _run(command: list[str], cwd: Path, timeout: float = 120) -> subprocess.CompletedProcess:
    proc = subprocess.run(command, cwd=cwd, text=True, capture_output=True, timeout=timeout, check=False)
    if proc.returncode:
        raise RuntimeError((proc.stderr or proc.stdout).strip())
    return proc


def _probe(path: Path) -> dict:
    proc = _run([
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration,size:stream=codec_name,width,height,pix_fmt,r_frame_rate",
        "-of", "json", str(path),
    ], path.parent)
    return json.loads(proc.stdout)


def export(recording: Path, output_name: str, reviewed: bool) -> int:
    if not reviewed:
        raise RuntimeError("inspect every renderer contact sheet, then rerun with --reviewed")
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise RuntimeError("ffmpeg and ffprobe are required")
    review_path = recording / "renderer-review.json"
    if not review_path.is_file():
        raise RuntimeError("run render_video.py review first")
    review_report = json.loads(review_path.read_text(encoding="utf-8"))
    if review_report.get("errors"):
        raise RuntimeError("renderer review has blocking errors")
    comp = load_composition(recording)
    if review_report.get("compositionMtimeNs") != (recording / "composition.js").stat().st_mtime_ns:
        raise RuntimeError("renderer review is stale; rerun it")
    renderer = recording / "video.html"
    if not renderer.is_file() or review_report.get("rendererSha256") != file_hash(renderer):
        raise RuntimeError("renderer changed after review; rerun it")
    if file_hash(renderer) != file_hash(TEMPLATE):
        raise RuntimeError("renderer is not the current shared template; rerun review")

    output = Path(output_name)
    if not output.is_absolute():
        output = recording / output
    if output.suffix.lower() != ".mp4":
        raise RuntimeError("--output must end in .mp4")
    webm = output.with_suffix(".webm")
    for path in (webm, output):
        if path.exists() or path.with_name(path.name + ".crdownload").exists():
            raise RuntimeError(f"refusing to overwrite {path}")

    expected = sum(float(beat.get("dur") or 0) for beat in comp.get("beats") or [])
    started = time.monotonic()
    with serve(recording) as url:
        try:
            browser = _start_export(recording, url, webm)
            if browser["preflight"].get("errors"):
                raise RuntimeError(
                    "export preflight failed: " + "; ".join(browser["preflight"]["errors"])
                )
            if any(not click.get("visible") for click in browser["clicks"]):
                raise RuntimeError("export click visibility failed")
            deadline = time.monotonic() + expected + 30
            partial = webm.with_name(webm.name + ".crdownload")
            while time.monotonic() < deadline:
                if webm.is_file() and not partial.exists() and webm.stat().st_size:
                    size = webm.stat().st_size
                    time.sleep(0.25)
                    if webm.stat().st_size == size:
                        break
                time.sleep(0.25)
            else:
                raise RuntimeError(f"timed out waiting for {webm}")
        finally:
            _close_editor(url)
    capture_seconds = time.monotonic() - started

    conversion_started = time.monotonic()
    _probe(webm)
    _run([
        "ffmpeg", "-v", "error", "-i", str(webm), "-c:v", "libx264",
        "-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(output),
    ], recording)
    conversion_seconds = time.monotonic() - conversion_started

    verify_started = time.monotonic()
    probe = _probe(output)
    actual = float(probe["format"]["duration"])
    if abs(actual - expected) > max(1.0, expected * 0.08):
        raise RuntimeError(f"export duration {actual:.2f}s does not match composition {expected:.2f}s")
    _run(["ffmpeg", "-v", "error", "-err_detect", "explode", "-i", str(output), "-f", "null", "-"], recording)

    review_dir = recording / ".renderer-review"
    final_captures = []
    for index, at in enumerate((min(1.0, expected / 4), expected / 2, max(0.0, expected - 0.8)), 1):
        path = review_dir / f"final-{index:02d}.jpg"
        _run(["ffmpeg", "-v", "error", "-y", "-ss", f"{at:.3f}", "-i", str(output), "-frames:v", "1", str(path)], recording)
        final_captures.append({"path": str(path), "time": at, "label": ("intro", "middle", "outcome")[index - 1]})
    final_sheet = recording / "renderer-final-contact-sheet.jpg"
    contact_sheet(final_captures, final_sheet, "FINAL MP4 SAMPLE")
    verify_seconds = time.monotonic() - verify_started

    report = {
        "output": str(output),
        "webm": str(webm),
        "expectedDuration": round(expected, 3),
        "actualDuration": actual,
        "captureSeconds": round(capture_seconds, 3),
        "conversionSeconds": round(conversion_seconds, 3),
        "verificationSeconds": round(verify_seconds, 3),
        "elapsedSeconds": round(time.monotonic() - started, 3),
        "sha256": file_hash(output),
        "probe": probe,
        "finalContactSheet": str(final_sheet),
    }
    report_path = recording / "video-export.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"video: {output}")
    print(f"final review: {final_sheet}")
    print(f"verified {actual:.2f}s MP4 in {report['elapsedSeconds']:.1f}s")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    review_parser = sub.add_parser("review")
    review_parser.add_argument("recording", type=Path)
    export_parser = sub.add_parser("export")
    export_parser.add_argument("recording", type=Path)
    export_parser.add_argument("--output", default="video.mp4")
    export_parser.add_argument("--reviewed", action="store_true")
    args = parser.parse_args()
    recording = args.recording.expanduser().resolve()
    try:
        if args.command == "review":
            return review(recording)
        return export(recording, args.output, args.reviewed)
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
