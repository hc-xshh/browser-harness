import importlib.util
import json
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
INIT_PATH = ROOT / "skills/browser-harness-video/scripts/init_video.py"
COMPOSE_PATH = ROOT / "skills/browser-harness-video/scripts/compose_video.py"
AUDIT_PATH = ROOT / "skills/browser-harness-video/scripts/audit_video.py"
RENDER_PATH = ROOT / "skills/browser-harness-video/scripts/render_video.py"
STYLE_PATH = ROOT / "skills/browser-harness-video/assets/house-style-v9.json"
TEMPLATE_PATH = ROOT / "interaction-skills/video-template.html"
VIDEO_SKILL_PATH = ROOT / "skills/browser-harness-video/SKILL.md"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


video_init = _load("browser_harness_video_init", INIT_PATH)
video_compose = _load("browser_harness_video_compose", COMPOSE_PATH)
video_audit = _load("browser_harness_video_audit", AUDIT_PATH)
video_render = _load("browser_harness_video_render", RENDER_PATH)
HOUSE_STYLE = json.loads(STYLE_PATH.read_text())


def test_codex_and_claude_first_run_instructions_route_to_the_video_skill():
    relative = "skills/browser-harness-video/SKILL.md"
    agents = (ROOT / "AGENTS.md").read_text()
    assert relative in agents
    assert "./browser-harness recordings --latest" in agents
    assert "delegate only video post-production" in agents
    assert "work alone is not consent" in agents
    assert relative in (ROOT / "CLAUDE.md").read_text()
    assert relative in (ROOT / "SKILL.md").read_text()
    video_skill = VIDEO_SKILL_PATH.read_text()
    assert "render_video.py review" in video_skill
    assert "renderer-click-contact-sheet.jpg" in video_skill
    assert "./browser-harness recordings --latest" in video_skill
    assert "Never reenact" in video_skill


def test_browser_skill_requires_user_intent_for_recording_and_video():
    skill = (ROOT / "SKILL.md").read_text()
    assert "Fresh installs do not record browser actions" in skill
    assert "Significant work alone is not consent" in skill
    assert "show me what you did" in skill
    assert "browser-harness recordings --latest" in skill
    assert "start_recording(name, title=...)" in skill


def test_install_asks_once_and_defaults_recording_consent_to_no():
    install = (ROOT / "install.md").read_text()
    assert "Enable local browser recordings?" in install
    assert "Default to no" in install
    assert "recordings enable" in install
    assert "Preserve an existing" in install


def _composition(intro: dict | None = None, middle: list[dict] | None = None) -> dict:
    return {
        "houseStyleVersion": HOUSE_STYLE["version"],
        "plan": ["Act", "Verify"],
        "frameStyle": HOUSE_STYLE["frameStyle"],
        "readingWpm": HOUSE_STYLE["readingWpm"],
        "pacing": HOUSE_STYLE["pacing"],
        "durationBudget": 22.0,
        "bg": HOUSE_STYLE["background"],
        "motion": HOUSE_STYLE["motion"],
        "privacy": {"reviewedFrames": []},
        "beats": [
            intro or {"card": True, "kind": "intro", "title": "Task", "dur": 4.5},
            *(middle or []),
            {
                "card": True,
                "kind": "outcome",
                "title": "Done",
                "outcomes": ["Verified"],
                "dur": 4.5,
            },
        ],
    }


def test_initializer_never_invents_product_specific_routes():
    route = video_init.safe_route_hint(
        "https://portal.azure.com/#view/Microsoft_AAD_UsersAndTenants/UserManagementMenuBlade"
    )
    assert route == "Browser"
    assert "azure" not in route.lower()


def test_audit_rejects_overlong_cards_without_a_linger_reason(tmp_path):
    comp = _composition(
        intro={"card": True, "kind": "intro", "title": "Task", "dur": 6.0}
    )
    errors, _, _ = video_audit.validate(tmp_path, comp)
    assert any("card is overlong" in error for error in errors)

    comp["beats"][0]["linger"] = "Pause for a narrated handoff"
    errors, _, _ = video_audit.validate(tmp_path, comp)
    assert not any("card is overlong" in error for error in errors)


def test_audit_requires_causal_failure_labels(tmp_path):
    explanation = {
        "card": True,
        "kind": "explanation",
        "title": "Why it failed",
        "points": [
            {"label": "Problem", "text": "It waited"},
            {"label": "Fix", "text": "Try again"},
        ],
        "dur": 4.0,
    }
    errors, _, _ = video_audit.validate(tmp_path, _composition(middle=[explanation]))
    assert any("Observed, Mistake, Correction" in error for error in errors)


def test_audit_requires_a_raw_end_state_hold_before_a_text_card(tmp_path):
    result = {
        "frame": "result.jpg",
        "route": "App / Result",
        "chapter": 1,
        "dur": 1.95,
    }
    comp = _composition(middle=[result])
    comp["durationBudget"] = 22.55
    errors, _, _ = video_audit.validate(tmp_path, comp)
    assert any("raw end state must hold" in error for error in errors)

    result["endStateHold"] = 0.55
    errors, _, _ = video_audit.validate(tmp_path, comp)
    assert not any("raw end state must hold" in error for error in errors)


def test_audit_blocks_unacknowledged_synthetic_browser_chrome(tmp_path):
    comp = _composition()
    comp["frameStyle"] = "browser"
    errors, _, _ = video_audit.validate(tmp_path, comp)
    assert any("synthetic browser chrome" in error for error in errors)

    comp["authenticity"] = {"allowSyntheticChrome": True}
    errors, _, _ = video_audit.validate(tmp_path, comp)
    assert any("frameStyle must match generated v9" in error for error in errors)


def _summary() -> dict:
    return {
        "events": [
            {
                "frame": "0001.jpg",
                "helper": "wait_for_load",
                "ts": 100.0,
                "viewport": {"w": 1392, "h": 1170},
                "cursor": None,
                "box": None,
                "text": None,
                "sensitive": False,
            },
            {
                "frame": "0002.jpg",
                "helper": "click_at_xy",
                "ts": 101.0,
                "viewport": {"w": 1392, "h": 1170},
                "cursor": {"x": 60, "y": 1138},
                "box": None,
                "text": None,
                "sensitive": False,
            },
            {
                "frame": "0003.jpg",
                "helper": "wait_for_load",
                "ts": 101.1,
                "viewport": {"w": 1392, "h": 1170},
                "cursor": None,
                "box": None,
                "text": None,
                "sensitive": False,
            },
        ]
    }


def _brief() -> dict:
    return {
        "task": "Complete the browser task",
        "summary": "Act, inspect the result, and verify it.",
        "plan": ["Act", "Verify"],
        "actions": [
            {
                "event": 2,
                "frameEvent": 1,
                "afterEvent": 3,
                "chapter": 0,
                "route": "App / Form",
                "afterRoute": "App / Result",
                "narration": "Apply the change.",
                "label": "Submit",
            }
        ],
        "outcomeTitle": "Change verified",
        "outcomes": ["Result confirmed"],
        "privacy": {
            "reviewedFrames": ["0001.jpg", "0003.jpg"],
            "redact": {},
        },
    }


def test_compiler_owns_the_complete_v9_house_style():
    comp = video_compose.compile_brief(_summary(), _brief(), HOUSE_STYLE)
    assert comp["houseStyleVersion"] == 9
    assert comp["frameStyle"] == "native"
    assert comp["readingWpm"] == 380
    assert comp["bg"] == ["#efece4", "#dce7e7"]
    assert comp["pacing"] == HOUSE_STYLE["pacing"]
    assert comp["durationBudget"] == 22.55
    assert comp["motion"] == HOUSE_STYLE["motion"]
    assert comp["privacy"]["mask"] == HOUSE_STYLE["privacy"]["mask"]
    action = comp["beats"][1]
    assert action["cursor"] == {"x": 60, "y": 1138}
    assert action["frame"] == "0001.jpg"
    assert action["click"] is True
    assert action["after"] == "0003.jpg"
    assert action["dur"] == 1.95
    assert action["endStateHold"] == 0.55
    assert comp["beats"][0]["dur"] >= 4.5
    assert comp["beats"][-1]["dur"] >= 4.5


def test_compiler_rejects_agent_authored_visual_tuning():
    brief = _brief()
    brief["actions"][0]["zoom"] = {"x": 60, "y": 1138, "scale": 2}
    with pytest.raises(video_compose.BriefError, match="unsupported field.*zoom"):
        video_compose.compile_brief(_summary(), brief, HOUSE_STYLE)


def test_compiler_rejects_a_brief_that_exceeds_the_pause_friendly_budget():
    brief = _brief()
    brief["task"] = " ".join(["detail"] * 120)
    with pytest.raises(video_compose.BriefError, match="budget is 22.6s"):
        video_compose.compile_brief(_summary(), brief, HOUSE_STYLE)


def test_renderer_keeps_bottom_edge_click_visible_and_reports_its_time():
    composition = {
        "houseStyleVersion": HOUSE_STYLE["version"],
        "viewport": {"w": 1392, "h": 1170},
        "cursorStart": {"x": 700, "y": 280},
        "frameStyle": "native",
        "readingWpm": HOUSE_STYLE["readingWpm"],
        "pacing": HOUSE_STYLE["pacing"],
        "durationBudget": 22.0,
        "plan": ["Act", "Verify"],
        "bg": HOUSE_STYLE["background"],
        "motion": HOUSE_STYLE["motion"],
        "privacy": {"reviewedFrames": ["before.jpg", "after.jpg"]},
        "beats": [
            {"card": True, "kind": "intro", "title": "Task", "dur": 4.5},
            {
                "frame": "before.jpg",
                "after": "after.jpg",
                "route": "App / Review",
                "chapter": 0,
                "cursor": {"x": 60, "y": 1138},
                "followScale": 1.5,
                "click": True,
                "label": "Confirm",
                "dur": 1.7,
            },
            {
                "card": True,
                "kind": "outcome",
                "title": "Done",
                "outcomes": ["Verified"],
                "dur": 4.5,
            },
        ],
    }
    node = r"""
const fs = require('fs');
const vm = require('vm');
const html = fs.readFileSync(process.argv[1], 'utf8');
const source = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].at(-1)[1];
const noop = () => {};
const gradient = {addColorStop: noop};
const ctx = new Proxy({}, {
  get(_target, key) {
    if (key === 'measureText') return text => ({width: String(text).length * 10});
    if (key === 'createLinearGradient' || key === 'createRadialGradient') return () => gradient;
    return noop;
  },
  set() { return true; },
});
const hud = {textContent: ''};
const sandbox = {
  window: {COMPOSITION: JSON.parse(process.argv[2])},
  document: {
    getElementById: id => id === 'stage' ? {getContext: () => ctx} : hud,
    createElement: () => ({click: noop}),
    addEventListener: noop,
  },
  matchMedia: () => ({matches: false}),
  Path2D: class {},
  Image: class { set src(_value) { queueMicrotask(() => this.onload?.()); } },
  requestAnimationFrame: noop,
  performance: {now: () => 0},
  MediaRecorder: {isTypeSupported: () => true},
  Blob: class {},
  URL: {createObjectURL: () => ''},
  console,
  Promise,
  queueMicrotask,
  setTimeout,
  clearTimeout,
};
vm.createContext(sandbox);
vm.runInContext(source, sandbox);
process.stdout.write(JSON.stringify({
  clicks: sandbox.window.clickVisibility(),
  preflight: sandbox.window.videoPreflight(),
}));
"""
    proc = subprocess.run(
        ["node", "-e", node, str(TEMPLATE_PATH), json.dumps(composition)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    click = result["clicks"][0]
    assert result["preflight"]["errors"] == []
    assert click["visible"] is True
    assert click["time"] > 4.5
    assert click["resultTime"] > click["time"]
    assert click["resultTime"] - click["time"] <= 0.08
    assert click["y"] <= 1080 - 190
    assert click["scale"] < 1.5


def test_renderer_review_samples_every_beat_and_explanation_reveal():
    comp = _composition(middle=[{
        "card": True,
        "kind": "explanation",
        "title": "Why it failed",
        "points": [
            {"label": "Observed", "text": "A guest form appeared"},
            {"label": "Mistake", "text": "The wrong account path was used"},
            {"label": "Correction", "text": "Create a member instead"},
        ],
        "dur": 5.0,
    }])

    samples = video_render.review_samples(comp)

    assert [sample["label"] for sample in samples] == [
        "beat 1",
        "beat 2 · Observed",
        "beat 2 · Mistake",
        "beat 2 · Correction",
        "beat 3",
    ]
    assert [sample["time"] for sample in samples] == sorted(
        sample["time"] for sample in samples
    )


def test_renderer_builds_a_compact_contact_sheet(tmp_path):
    captures = []
    for index, color in enumerate(("red", "green", "blue"), 1):
        path = tmp_path / f"frame-{index}.png"
        video_render.Image.new("RGB", (1920, 1080), color).save(path)
        captures.append({"path": str(path), "time": index, "label": f"beat {index}"})

    output = tmp_path / "sheet.jpg"
    video_render.contact_sheet(captures, output, "REVIEW")

    with video_render.Image.open(output) as sheet:
        assert sheet.width == 1640
        assert sheet.height < 400


def test_renderer_starts_export_without_blocking_the_harness(monkeypatch, tmp_path):
    captured = {}

    def fake_run_harness(code, timeout):
        captured["code"] = code
        captured["timeout"] = timeout
        return {"started": True}

    monkeypatch.setattr(video_render, "run_harness", fake_run_harness)

    result = video_render._start_export(
        tmp_path, "http://127.0.0.1/video.html", tmp_path / "sample.webm"
    )

    compile(captured["code"], "<browser-harness-export>", "exec")
    assert result == {"started": True}
    assert captured["timeout"] == 30
    assert 'window.exportVideo("sample.webm")' in captured["code"]
    assert "await" not in captured["code"]


def test_renderer_export_requires_explicit_contact_sheet_review(tmp_path):
    with pytest.raises(RuntimeError, match="inspect every renderer contact sheet"):
        video_render.export(tmp_path, "video.mp4", reviewed=False)
