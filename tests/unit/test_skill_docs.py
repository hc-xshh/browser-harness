from pathlib import Path


def test_packaged_skill_points_to_root_skill():
    repo = Path(__file__).resolve().parents[2]
    skill = repo / "skills" / "browser-harness" / "SKILL.md"

    assert skill.is_symlink()
    assert skill.readlink() == Path("../../SKILL.md")
