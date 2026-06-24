from src.llm_client import chat
from src.skills import load_skill
from src.agents import STYLE_GUIDE, parse_json

_SKILL = load_skill("resume-optimizer")

_SYSTEM = f"""{_SKILL}

{STYLE_GUIDE}

Return your rewrites as a single JSON object. Schema:
{{
  "rewrites": [
    {{
      "original": "<exact original bullet text>",
      "optimized": "<XYZ-formula rewritten bullet, no semicolons, no em dashes>",
      "what_changed": "<one-line explanation>"
    }}
  ]
}}
Rules:
- Rewrite every bullet. Do not add or remove bullets.
- Lead with result, then metric, then method.
- Use active verbs. No weak openers like responsible for or helped with.
- Avoid semicolons. Split into two bullets if needed.
- Every bullet must include a number or a concrete scope.
Return ONLY the JSON. No markdown fences. No extra text.
"""


def optimize_bullets(resume_text: str, jd_match: dict) -> dict:
    keywords = ", ".join(
        k["keyword"] for k in jd_match.get("missing_keywords", [])[:10]
        if k.get("importance") in ("Critical", "High", "Medium")
    )
    prompt = (
        f"Resume:\n{resume_text}\n\n"
        f"Priority keywords to work in naturally where they fit: {keywords}\n\n"
        "Rewrite every bullet using the XYZ formula."
    )
    raw = chat(_SYSTEM, prompt)
    return parse_json(raw, {"rewrites": []})
