"""Load skill system prompts from src/skills/<name>/SKILL.md."""
from pathlib import Path

_SKILLS_DIR = Path(__file__).parent / "skills"


def load_skill(name: str) -> str:
    path = _SKILLS_DIR / name / "SKILL.md"
    if not path.exists():
        return f"You are an expert {name.replace('-', ' ')} assistant."
    return path.read_text(encoding="utf-8")
